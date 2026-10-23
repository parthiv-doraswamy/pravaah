"""Read-only policy-to-proof dossier for one application."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.routes.applications import scoped_applications_statement
from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.models.core import Application, User
from app.models.evidence import ApplicationEvidence
from app.models.evidence_attachment import EvidenceAttachment
from app.models.escalation import ComplianceEscalation
from app.models.evc_visit import EVCVisit
from app.models.notification import NotificationRecord
from app.models.undertaking import ComplianceSubmission
from app.models.workflow import ApplicationEvent, PolicyVersion
from app.services.workflow import verify_event_chain

router = APIRouter()


@router.get(
    "/{application_id}/policy-to-proof",
    summary="Build an auditable policy-to-proof dossier for an application",
)
def policy_to_proof_dossier(
    application_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Link policy provenance, evidence, review activity, EVC and delivery records.

    The dossier is explanatory evidence for human review, not a statutory decision
    or an assertion that synthetic demo policies are official requirements.
    """
    application = db.scalar(
        scoped_applications_statement(user).where(Application.id == application_id)
    )
    if application is None:
        # Avoid confirming that an out-of-scope application exists.
        raise HTTPException(status_code=404, detail="Application not found")

    evidence = db.scalars(
        select(ApplicationEvidence)
        .where(ApplicationEvidence.application_id == application.id)
        .order_by(ApplicationEvidence.created_at, ApplicationEvidence.id)
        .limit(500)
    ).all()
    events = db.scalars(
        select(ApplicationEvent)
        .where(ApplicationEvent.application_id == application.id)
        .order_by(ApplicationEvent.sequence)
        .limit(1000)
    ).all()
    submissions = db.scalars(
        select(ComplianceSubmission)
        .where(ComplianceSubmission.application_id == application.id)
        .order_by(ComplianceSubmission.created_at, ComplianceSubmission.id)
        .limit(500)
    ).all()
    visits = db.scalars(
        select(EVCVisit)
        .where(EVCVisit.application_id == application.id)
        .order_by(EVCVisit.scheduled_for, EVCVisit.id)
        .limit(200)
    ).all()
    notifications = db.scalars(
        select(NotificationRecord)
        .where(NotificationRecord.application_id == application.id)
        .order_by(NotificationRecord.created_at, NotificationRecord.id)
        .limit(500)
    ).all()
    escalations = db.scalars(
        select(ComplianceEscalation)
        .where(ComplianceEscalation.application_id == application.id)
        .order_by(ComplianceEscalation.triggered_at, ComplianceEscalation.id)
        .limit(500)
    ).all()

    evidence_ids = [item.id for item in evidence]
    attachments = []
    if evidence_ids:
        attachments = db.scalars(
            select(EvidenceAttachment)
            .where(
                EvidenceAttachment.application_id == application.id,
                EvidenceAttachment.evidence_id.in_(evidence_ids),
            )
            .order_by(EvidenceAttachment.created_at, EvidenceAttachment.id)
            .limit(500)
        ).all()

    policy_keys = {item.policy_key for item in evidence if item.policy_key}
    for event in events:
        key = (event.event_metadata or {}).get("policy_key")
        if isinstance(key, str) and key:
            policy_keys.add(key)
    policies = []
    if policy_keys:
        policies = db.scalars(
            select(PolicyVersion)
            .where(PolicyVersion.policy_key.in_(sorted(policy_keys)))
            .order_by(PolicyVersion.policy_key, PolicyVersion.version)
            .limit(500)
        ).all()

    chain_valid, first_invalid_sequence = verify_event_chain(events)
    return {
        "as_of": __import__("datetime").datetime.now(__import__("datetime").UTC),
        "disclaimer": (
            "Traceability dossier for human review. Policy records may be synthetic "
            "demo assumptions and are not official AICTE rules or a statutory decision."
        ),
        "application": {
            "id": str(application.id),
            "application_number": application.application_number,
            "title": application.title,
            "status": application.status,
            "institution_id": str(application.institution_id),
            "created_at": application.created_at,
            "updated_at": application.updated_at,
        },
        "policy_versions": [
            {
                "id": str(item.id),
                "policy_key": item.policy_key,
                "version": item.version,
                "title": item.title,
                "description": item.description,
                "effective_from": item.effective_from,
                "rules_schema_version": item.rules_schema_version,
                "source_label": item.source_label,
                "is_active": item.is_active,
            }
            for item in policies
        ],
        "evidence": [
            {
                "id": str(item.id),
                "title": item.title,
                "category": item.category,
                "reference_number": item.reference_number,
                "version": item.version,
                "supersedes_evidence_id": str(item.supersedes_evidence_id) if item.supersedes_evidence_id else None,
                "lifecycle_status": item.lifecycle_status,
                "issued_on": item.issued_on,
                "expires_on": item.expires_on,
                "policy_key": item.policy_key,
                "notes": item.notes,
                "created_at": item.created_at,
            }
            for item in evidence
        ],
        "attachments": [
            {
                "id": str(item.id),
                "evidence_id": str(item.evidence_id),
                "filename": item.original_filename,
                "content_type": item.content_type,
                "size_bytes": item.size_bytes,
                "sha256": item.sha256_hex,
                "created_at": item.created_at,
            }
            for item in attachments
        ],
        "compliance_submissions": [
            {
                "id": str(item.id),
                "submission_type": item.submission_type,
                "title": item.title,
                "status": item.status,
                "version": item.version,
                "evidence_ids": item.evidence_ids or [],
                "supersedes_submission_id": str(item.supersedes_submission_id) if item.supersedes_submission_id else None,
                "submitted_at": item.submitted_at,
                "reviewed_at": item.reviewed_at,
                "review_notes": item.review_notes,
            }
            for item in submissions
        ],
        "evc_visits": [
            {
                "id": str(item.id),
                "scheduled_for": item.scheduled_for,
                "mode": item.mode,
                "location": item.location,
                "status": item.status,
                "report_status": item.report_status,
                "report_submitted_at": item.report_submitted_at,
                "linked_evidence_ids": item.linked_evidence_ids or [],
                "outcome_summary": item.outcome_summary,
                "observations": item.observations,
            }
            for item in visits
        ],
        "notifications": [
            {
                "id": str(item.id),
                "notification_type": item.notification_type,
                "title": item.title,
                "severity": item.severity,
                "delivery_status": item.delivery_status,
                "attempt_count": item.attempt_count,
                "max_attempts": item.max_attempts,
                "last_error": item.last_error,
                "created_at": item.created_at,
                "sent_at": item.sent_at,
            }
            for item in notifications
        ],
        "escalations": [
            {
                "id": str(item.id),
                "evidence_id": str(item.evidence_id),
                "type": item.escalation_type,
                "status": item.status,
                "severity": item.severity,
                "summary": item.summary,
                "triggered_at": item.triggered_at,
                "resolved_at": item.resolved_at,
            }
            for item in escalations
        ],
        "audit": {
            "event_count": len(events),
            "valid": chain_valid,
            "first_invalid_sequence": first_invalid_sequence,
            "events": [
                {
                    "id": str(item.id),
                    "sequence": item.sequence,
                    "event_type": item.event_type,
                    "from_status": item.from_status,
                    "to_status": item.to_status,
                    "actor_user_id": str(item.actor_user_id) if item.actor_user_id else None,
                    "reason": item.reason,
                    "metadata": item.event_metadata or {},
                    "occurred_at": item.occurred_at,
                    "previous_hash": item.previous_hash,
                    "event_hash": item.event_hash,
                }
                for item in events
            ],
        },
        "counts": {
            "policy_versions": len(policies),
            "evidence": len(evidence),
            "attachments": len(attachments),
            "compliance_submissions": len(submissions),
            "evc_visits": len(visits),
            "notifications": len(notifications),
            "escalations": len(escalations),
        },
    }
