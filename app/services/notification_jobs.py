"""Scheduled, idempotent expiry notification and escalation jobs."""

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.core.clock import utc_now, utc_today
from app.models.core import Application, Institution, User
from app.models.evidence import ApplicationEvidence
from app.models.evc_visit import EVCVisit
from app.models.workflow import ApplicationEvent
from app.models.escalation import ComplianceEscalation
from app.models.notification import NotificationRecord
from app.services.workflow import active_workflow_policy, append_event
from app.schemas.policy_rules import PolicyDeadlineRule, validate_policy_rules

ESCALATION_AFTER_DAYS = 7

_REVIEW_RECIPIENT_ROLES = {
    "submitted": {"scrutiny_officer", "regional_officer", "bureau_officer"},
    "clarification_requested": {"institution_user"},
    "evc_report_due": {"evc_coordinator", "bureau_officer"},
}


def _active_deadline_rules(db: Session) -> dict[str, PolicyDeadlineRule]:
    policy = active_workflow_policy(db)
    if policy is None:
        return {}
    try:
        rules = validate_policy_rules(policy.rules_schema_version, policy.rules)
    except (ValueError, TypeError) as exc:
        # Runtime policy corruption must not silently create guessed deadlines.
        raise RuntimeError("Active workflow policy contains invalid deadline rules") from exc
    return {rule.event: rule for rule in rules.deadlines}



def _insert_if_absent(db: Session, model, values: dict) -> bool:
    """Insert a deduplicated record atomically on supported production/test databases."""
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        statement = postgres_insert(model).values(**values)
    elif dialect == "sqlite":
        statement = sqlite_insert(model).values(**values)
    else:
        raise RuntimeError(f"Unsupported database dialect for deduplicated queue writes: {dialect}")

    result = db.execute(
        statement.on_conflict_do_nothing(index_elements=[model.dedupe_key]).returning(model.id)
    )
    return result.scalar_one_or_none() is not None


def expiry_severity(expires_on: date, today: date) -> tuple[str, int] | None:
    """Classify an expiry date using the shared, explicitly supplied calendar date."""
    days = (expires_on - today).days
    if days < 0:
        return "expired", days
    if days <= 1:
        return "urgent", days
    if days <= 7:
        return "warning", days
    if days <= 30:
        return "upcoming", days
    return None


def run_expiry_monitoring(db: Session, today: date | None = None) -> dict[str, int | str]:
    """Queue deduplicated in-app reminders and open escalations for long-expired evidence."""
    now = utc_now()
    run_date = today if today is not None else utc_today(now)
    deadline_rule = _active_deadline_rules(db).get("evidence_expiry")
    escalation_after = (
        deadline_rule.escalation_days_after
        if deadline_rule is not None
        else ESCALATION_AFTER_DAYS
    )
    rows = db.execute(
        select(ApplicationEvidence, Application, User)
        .join(Application, Application.id == ApplicationEvidence.application_id)
        .join(User, User.institution_id == Application.institution_id)
        .where(
            User.role == "institution_user",
            User.is_active.is_(True),
            ApplicationEvidence.expires_on.is_not(None),
        )
        .order_by(ApplicationEvidence.expires_on.asc())
    ).all()

    queued = 0
    skipped = 0
    escalated = 0
    audited: set[tuple[str, str]] = set()

    for evidence, application, recipient in rows:
        days = (evidence.expires_on - run_date).days
        if deadline_rule is not None:
            if days < 0:
                severity = "expired"
            elif days in deadline_rule.reminder_days_before:
                severity = "urgent" if days <= 1 else ("warning" if days <= 7 else "upcoming")
            else:
                continue
        else:
            classified = expiry_severity(evidence.expires_on, run_date)
            if classified is None:
                continue
            severity, days = classified
        day_text = "expired" if days < 0 else (
            "expires today" if days == 0 else f"expires in {days} day{'s' if days != 1 else ''}"
        )
        notification_key = (
            f"expiry:{evidence.id}:{evidence.expires_on.isoformat()}:{severity}:{recipient.id}"
        )
        inserted = _insert_if_absent(db, NotificationRecord, {
            "id": uuid4(),
            "recipient_user_id": recipient.id,
            "application_id": application.id,
            "evidence_id": evidence.id,
            "dedupe_key": notification_key,
            "notification_type": "evidence_expiry",
            "title": f"Evidence {day_text}: {evidence.title}",
            "message": f"{application.application_number} — {application.title}. {evidence.title} {day_text}. Review the record and arrange any required follow-up.",
            "severity": severity,
            "delivery_status": "pending",
            "attempt_count": 0,
            "max_attempts": 5,
            "next_attempt_at": now,
            "created_at": now,
            "updated_at": now,
        })
        if inserted:
            queued += 1
            key = (str(evidence.id), "expiry_notification_queued")
            if key not in audited:
                append_event(
                    db, application_id=application.id, event_type="expiry_notification_queued",
                    from_status=application.status, to_status=application.status, actor_user_id=None,
                    metadata={"evidence_id": str(evidence.id), "severity": severity,
                              "days_remaining": days, "notification_date": run_date.isoformat(),
                              "source": "scheduled_worker"},
                )
                db.flush()
                audited.add(key)
        else:
            skipped += 1

        if escalation_after is not None and days < -escalation_after:
            escalation_key = f"expired:{evidence.id}:{evidence.expires_on.isoformat()}:after-{escalation_after}d"
            escalation_summary = (
                f"{evidence.title} expired on {evidence.expires_on.isoformat()} and remains expired "
                f"beyond the configured {escalation_after}-day escalation threshold."
            )
            inserted_escalation = _insert_if_absent(db, ComplianceEscalation, {
                "id": uuid4(),
                "dedupe_key": escalation_key,
                "application_id": application.id,
                "evidence_id": evidence.id,
                "escalation_type": "evidence_expired",
                "status": "open",
                "severity": "high",
                "summary": escalation_summary,
                "triggered_at": now,
            })
            escalation = db.scalar(
                select(ComplianceEscalation).where(ComplianceEscalation.dedupe_key == escalation_key)
            )
            if inserted_escalation:
                escalated += 1
                append_event(
                    db, application_id=application.id, event_type="compliance_escalation_opened",
                    from_status=application.status, to_status=application.status, actor_user_id=None,
                    metadata={"escalation_id": str(escalation.id), "evidence_id": str(evidence.id),
                              "severity": "high", "days_expired": abs(days),
                              "threshold_days": escalation_after, "source": "scheduled_worker"},
                )
                db.flush()
            escalation_notification_key = f"escalation:{escalation.id}:{recipient.id}"
            escalation_notification_inserted = _insert_if_absent(db, NotificationRecord, {
                "id": uuid4(),
                "recipient_user_id": recipient.id,
                "application_id": application.id,
                "evidence_id": evidence.id,
                "dedupe_key": escalation_notification_key,
                "notification_type": "compliance_escalation",
                "title": f"Compliance escalation: {evidence.title}",
                "message": escalation.summary,
                "severity": "escalation",
                "delivery_status": "pending",
                "attempt_count": 0,
                "max_attempts": 5,
                "next_attempt_at": now,
                "created_at": now,
                "updated_at": now,
            })
            if escalation_notification_inserted:
                queued += 1
            else:
                skipped += 1

    db.commit()
    return {
        "as_of": run_date.isoformat(),
        # Rows are joined to institution users; count each evidence record only once.
        "evidence_records_checked": len({str(evidence.id) for evidence, _, _ in rows}),
        "notifications_queued": queued,
        "existing_notifications_skipped": skipped,
        "escalations_opened": escalated,
    }



def run_policy_deadline_monitoring(
    db: Session, now: datetime | None = None
) -> dict[str, int | str]:
    """Queue policy-driven workflow deadline reminders and overdue escalation notices."""
    run_at = now or utc_now()
    if run_at.tzinfo is None or run_at.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    run_at = run_at.astimezone(UTC)
    run_date = run_at.date()
    deadline_rules = _active_deadline_rules(db)
    if not deadline_rules:
        return {
            "as_of": run_at.isoformat(),
            "deadline_events_checked": 0,
            "notifications_queued": 0,
            "existing_notifications_skipped": 0,
            "escalations_notified": 0,
        }

    candidates: list[tuple[Application, str, datetime, str]] = []
    status_events = db.scalars(
        select(ApplicationEvent).where(
            ApplicationEvent.event_type == "status_transition",
            ApplicationEvent.to_status.in_(["submitted", "clarification_requested"]),
        ).order_by(ApplicationEvent.sequence.desc())
    ).all()
    latest_status_event: set[tuple[str, str]] = set()
    for event in status_events:
        event_name = event.to_status
        rule = deadline_rules.get(event_name)
        if rule is None:
            continue
        key = (str(event.application_id), event_name)
        if key in latest_status_event:
            continue
        latest_status_event.add(key)
        application = db.get(Application, event.application_id)
        if application is None or application.status != event_name:
            continue
        candidates.append((application, event_name, event.occurred_at, f"event-{event.sequence}"))

    evc_rule = deadline_rules.get("evc_report_due")
    if evc_rule is not None:
        visits = db.scalars(
            select(EVCVisit).where(
                EVCVisit.status == "completed",
                EVCVisit.report_status != "submitted",
            )
        ).all()
        for visit in visits:
            completion_event = db.scalar(
                select(ApplicationEvent).where(
                    ApplicationEvent.application_id == visit.application_id,
                    ApplicationEvent.event_type == "evc_visit_status_changed",
                    ApplicationEvent.to_status == "completed",
                ).order_by(ApplicationEvent.sequence.desc()).limit(1)
            )
            if completion_event is None:
                continue
            if str(visit.id) != str((completion_event.event_metadata or {}).get("visit_id", "")):
                continue
            application = db.get(Application, visit.application_id)
            if application is not None:
                candidates.append((
                    application, "evc_report_due", completion_event.occurred_at,
                    f"visit-{visit.id}",
                ))

    queued = skipped = escalations = 0
    audited: set[tuple[str, str]] = set()
    for application, event_name, occurred_at, source_key in candidates:
        rule = deadline_rules.get(event_name)
        if rule is None:
            continue
        base_at = occurred_at
        if base_at.tzinfo is None:
            base_at = base_at.replace(tzinfo=UTC)
        due_date = (base_at.astimezone(UTC) + timedelta(days=rule.deadline_days)).date()
        days_remaining = (due_date - run_date).days
        is_reminder = days_remaining in rule.reminder_days_before
        is_escalation = (
            rule.escalation_days_after is not None
            and days_remaining <= -rule.escalation_days_after
        )
        if not is_reminder and not is_escalation:
            continue

        institution = db.get(Institution, application.institution_id)
        roles = (
            {"bureau_officer", "competent_authority", "system_admin"}
            if is_escalation
            else _REVIEW_RECIPIENT_ROLES[event_name]
        )
        users = db.scalars(
            select(User).where(User.is_active.is_(True), User.role.in_(roles))
        ).all()
        for recipient in users:
            if recipient.role == "institution_user" and recipient.institution_id != application.institution_id:
                continue
            if recipient.role == "regional_officer":
                recipient_institution = (
                    db.get(Institution, recipient.institution_id)
                    if recipient.institution_id is not None else None
                )
                if (
                    institution is None or recipient_institution is None
                    or recipient_institution.region_code != institution.region_code
                ):
                    continue
            kind = (
                f"escalation-{rule.escalation_days_after}"
                if is_escalation else f"reminder-{days_remaining}"
            )
            dedupe_key = (
                f"workflow-deadline:{application.id}:{event_name}:{source_key}:"
                f"{kind}:{recipient.id}"
            )
            day_label = (
                f"{abs(days_remaining)} day{'s' if abs(days_remaining) != 1 else ''} overdue"
                if days_remaining < 0 else (
                    "due today" if days_remaining == 0
                    else f"due in {days_remaining} day{'s' if days_remaining != 1 else ''}"
                )
            )
            is_new = _insert_if_absent(db, NotificationRecord, {
                "id": uuid4(),
                "recipient_user_id": recipient.id,
                "application_id": application.id,
                "evidence_id": None,
                "dedupe_key": dedupe_key,
                "notification_type": (
                    "workflow_deadline_escalation" if is_escalation
                    else "workflow_deadline_reminder"
                ),
                "title": (
                    f"Workflow deadline escalation: {application.application_number}"
                    if is_escalation else f"Workflow deadline reminder: {application.application_number}"
                ),
                "message": (
                    f"{application.application_number} — {application.title}: "
                    f"{event_name.replace('_', ' ')} deadline is {day_label}. "
                    "Review the case and take the appropriate human action."
                ),
                "severity": "escalation" if is_escalation else "warning",
                "delivery_status": "pending",
                "attempt_count": 0,
                "max_attempts": 5,
                "next_attempt_at": run_at,
                "created_at": run_at,
                "updated_at": run_at,
            })
            if is_new:
                queued += 1
                if is_escalation:
                    escalations += 1
                audit_key = (str(application.id), f"{event_name}:{source_key}:{kind}")
                if audit_key not in audited:
                    append_event(
                        db,
                        application_id=application.id,
                        event_type=(
                            "workflow_deadline_escalation_notified"
                            if is_escalation else "workflow_deadline_reminder_queued"
                        ),
                        from_status=application.status,
                        to_status=application.status,
                        actor_user_id=None,
                        metadata={
                            "deadline_event": event_name,
                            "source_key": source_key,
                            "policy_deadline_days": rule.deadline_days,
                            "due_date": due_date.isoformat(),
                            "days_remaining": days_remaining,
                            "escalation_days_after": rule.escalation_days_after,
                            "policy_version": active_workflow_policy(db).version
                            if active_workflow_policy(db) else None,
                            "source": "scheduled_worker",
                        },
                    )
                    audited.add(audit_key)
            else:
                skipped += 1

    db.commit()
    return {
        "as_of": run_at.isoformat(),
        "deadline_events_checked": len(candidates),
        "notifications_queued": queued,
        "existing_notifications_skipped": skipped,
        "escalations_notified": escalations,
    }
