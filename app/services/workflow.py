"""Guarded application state transitions and event-chain utilities."""

import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.core import Application, User
from app.models.workflow import ApplicationEvent

# Final approval/rejection remains an explicit human action by the competent authority.
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
ZERO_HASH = "0" * 64


def canonical_event_hash(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def append_event(
    db: Session, *, application_id: UUID, event_type: str, from_status: str | None,
    to_status: str | None, actor_user_id: UUID | None, reason: str | None = None,
    metadata: dict | None = None,
) -> ApplicationEvent:
    """Append one chained event within the caller's transaction.

    Lock the parent application before reading the chain head so concurrent writers
    for the same application serialize on databases that support row-level locks.
    """
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
    # Flush before returning so a second append in the same transaction sees this
    # event as the current chain head and receives the next sequence number.
    db.flush()
    return event


def transition_application(
    db: Session, *, application: Application, actor: User, target_status: str,
    expected_status: str, reason: str | None = None,
) -> Application:
    """Lock and refresh the case before validating and applying a transition."""
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
    allowed = TRANSITIONS.get(application.status, {}).get(actor.role, set())
    if target_status not in allowed:
        raise HTTPException(
            status_code=409,
            detail=f"Transition '{application.status}' to '{target_status}' is not allowed for role '{actor.role}'",
        )
    previous = application.status
    application.status = target_status
    if target_status == "submitted" and application.submitted_at is None:
        application.submitted_at = datetime.now(UTC)
    append_event(
        db, application_id=application.id, event_type="status_transition",
        from_status=previous, to_status=target_status, actor_user_id=actor.id, reason=reason,
    )
    db.commit()
    db.refresh(application)
    return application


def verify_event_chain(events: list[ApplicationEvent]) -> tuple[bool, int | None]:
    """Verify event sequence, previous links, and content hashes."""
    previous_hash = ZERO_HASH
    for expected_sequence, event in enumerate(events, start=1):
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
