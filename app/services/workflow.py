"""Guarded application state transitions and event-chain utilities."""

import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.core import Application, User
from app.models.evidence import ApplicationEvidence
from app.models.workflow import ApplicationEvent, PolicyVersion
from app.schemas.policy_rules import validate_policy_rules

# Compatibility path for installations that have not activated a workflow policy.
# Final approval/rejection remains reserved for a competent authority.
TRANSITIONS: dict[str, dict[str, set[str]]] = {
    "draft": {"institution_user": {"submitted"}},
    "submitted": {"scrutiny_officer": {"under_scrutiny", "clarification_requested"}},
    "clarification_requested": {"institution_user": {"submitted"}},
    "under_scrutiny": {"scrutiny_officer": {"clarification_requested", "recommended_for_approval", "returned"}},
    "returned": {"institution_user": {"submitted"}},
    "recommended_for_approval": {"bureau_officer": {"pending_authority_decision"}},
    "pending_authority_decision": {"competent_authority": {"approved", "rejected"}},
    "approved": {},
    "rejected": {},
}
WORKFLOW_POLICY_KEY = "application_workflow"
ZERO_HASH = "0" * 64


def canonical_event_hash(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def active_workflow_policy(db: Session) -> PolicyVersion | None:
    """Return the latest effective, active application workflow policy, if any."""
    now = datetime.now(UTC)
    policies = db.scalars(
        select(PolicyVersion)
        .where(PolicyVersion.policy_key == WORKFLOW_POLICY_KEY, PolicyVersion.is_active.is_(True))
        .order_by(PolicyVersion.version.desc())
    ).all()
    for policy in policies:
        effective_from = policy.effective_from
        if effective_from.tzinfo is None:
            effective_from = effective_from.replace(tzinfo=UTC)
        if effective_from <= now:
            return policy
    return None


def append_event(
    db: Session, *, application_id: UUID, event_type: str, from_status: str | None,
    to_status: str | None, actor_user_id: UUID | None, reason: str | None = None,
    metadata: dict | None = None,
) -> ApplicationEvent:
    """Append one chained event within the caller's transaction."""
    db.scalar(
        select(Application.id).where(Application.id == application_id).with_for_update()
    )
    previous = db.scalar(
        select(ApplicationEvent).where(ApplicationEvent.application_id == application_id)
        .order_by(ApplicationEvent.sequence.desc()).limit(1)
    )
    sequence = previous.sequence + 1 if previous else 1
    previous_hash = previous.event_hash if previous else ZERO_HASH
    occurred_at = datetime.now(UTC)
    event_metadata = metadata or {}
    payload = {
        "application_id": str(application_id), "sequence": sequence, "event_type": event_type,
        "from_status": from_status, "to_status": to_status,
        "actor_user_id": str(actor_user_id) if actor_user_id else None,
        "reason": reason, "metadata": event_metadata, "occurred_at": occurred_at.isoformat(),
        "previous_hash": previous_hash,
    }
    event = ApplicationEvent(
        application_id=application_id, sequence=sequence, event_type=event_type,
        from_status=from_status, to_status=to_status, actor_user_id=actor_user_id,
        reason=reason, event_metadata=event_metadata, occurred_at=occurred_at,
        previous_hash=previous_hash, event_hash=canonical_event_hash(payload),
    )
    db.add(event)
    db.flush()
    return event


def _check_prerequisites(db: Session, application: Application, policy: PolicyVersion, target_status: str) -> None:
    try:
        rules = validate_policy_rules(policy.rules_schema_version, policy.rules)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=503, detail="Active workflow policy is invalid; transition blocked") from exc
    prerequisite = next((rule for rule in rules.prerequisites if rule.status == target_status), None)
    if prerequisite is None:
        return
    missing_fields = [
        field for field in prerequisite.required_fields
        if getattr(application, field, None) in (None, "")
    ]
    if missing_fields:
        raise HTTPException(
            status_code=409,
            detail={"message": "Application prerequisites are not met", "missing_fields": missing_fields},
        )
    if prerequisite.required_evidence_categories:
        present = set(db.scalars(
            select(ApplicationEvidence.category).where(
                ApplicationEvidence.application_id == application.id,
                ApplicationEvidence.category.in_(prerequisite.required_evidence_categories),
            )
        ).all())
        missing_evidence = sorted(set(prerequisite.required_evidence_categories) - present)
        if missing_evidence:
            raise HTTPException(
                status_code=409,
                detail={"message": "Required evidence is missing", "missing_evidence_categories": missing_evidence},
            )


def transition_application(
    db: Session, *, application: Application, actor: User, target_status: str,
    expected_status: str, reason: str | None = None,
) -> Application:
    """Lock, refresh, validate policy/prerequisites, and apply one human transition."""
    locked_application = db.scalar(
        select(Application)
        .where(Application.id == application.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if locked_application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    application = locked_application
    if application.status != expected_status:
        raise HTTPException(status_code=409, detail=f"Application status changed; current status is '{application.status}'")

    policy = active_workflow_policy(db)
    if policy is None:
        allowed = TRANSITIONS.get(application.status, {}).get(actor.role, set())
        if target_status not in allowed:
            raise HTTPException(
                status_code=409,
                detail=f"Transition '{application.status}' to '{target_status}' is not allowed for role '{actor.role}'",
            )
    else:
        try:
            rules = validate_policy_rules(policy.rules_schema_version, policy.rules)
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=503, detail="Active workflow policy is invalid; transition blocked") from exc
        matching = next(
            (rule for rule in rules.transitions
             if rule.from_status == application.status and rule.to_status == target_status),
            None,
        )
        if matching is None or actor.role not in matching.allowed_roles:
            raise HTTPException(
                status_code=409,
                detail=f"Transition '{application.status}' to '{target_status}' is not allowed by active policy",
            )
        if matching.requires_human_approval and actor.id is None:
            raise HTTPException(status_code=403, detail="This transition requires an authenticated human decision")
        _check_prerequisites(db, application, policy, target_status)

    if target_status in {"approved", "rejected"} and actor.role != "competent_authority":
        raise HTTPException(status_code=403, detail="Final decisions require the competent authority")
    previous = application.status
    application.status = target_status
    if target_status == "submitted" and application.submitted_at is None:
        application.submitted_at = datetime.now(UTC)
    event_metadata = {}
    if policy is not None:
        event_metadata = {
            "policy_key": policy.policy_key,
            "policy_version": policy.version,
            "policy_rules_schema_version": policy.rules_schema_version,
        }
    append_event(
        db, application_id=application.id, event_type="status_transition",
        from_status=previous, to_status=target_status, actor_user_id=actor.id,
        reason=reason, metadata=event_metadata,
    )
    db.commit()
    db.refresh(application)
    return application


def verify_event_chain(events: list[ApplicationEvent]) -> tuple[bool, int | None]:
    """Verify event sequence, a single application scope, previous links, and hashes."""
    previous_hash = ZERO_HASH
    chain_application_id = events[0].application_id if events else None
    for expected_sequence, event in enumerate(events, start=1):
        if event.application_id != chain_application_id:
            return False, event.sequence
        occurred_at = event.occurred_at
        if occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=UTC)
        payload = {
            "application_id": str(event.application_id), "sequence": event.sequence,
            "event_type": event.event_type, "from_status": event.from_status, "to_status": event.to_status,
            "actor_user_id": str(event.actor_user_id) if event.actor_user_id else None,
            "reason": event.reason, "metadata": event.event_metadata or {},
            "occurred_at": occurred_at.isoformat(), "previous_hash": event.previous_hash,
        }
        if event.sequence != expected_sequence or event.previous_hash != previous_hash or event.event_hash != canonical_event_hash(payload):
            return False, event.sequence
        previous_hash = event.event_hash
    return True, None
