"""Scoped pendency analytics endpoint."""

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.routes.applications import scoped_applications_statement
from app.auth.dependencies import get_current_user
from app.core.clock import utc_today
from app.db.session import get_db
from app.models.core import Application, User
from app.schemas.operations import PendencyAnalytics, PendencyItem, PendencyStatusSummary

router = APIRouter()
PENDING_STATUSES = {
    "submitted", "scrutiny", "under_scrutiny", "re_scrutiny",
    "awaiting_institution_response", "clarification_requested",
    "committee_review", "pending_authority_decision", "decision_pending",
}


@router.get("", response_model=PendencyAnalytics)
def get_pendency_analytics(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PendencyAnalytics:
    """Summarize waiting time for visible applications currently in review."""
    today = utc_today()
    statement = scoped_applications_statement(user).where(Application.status.in_(PENDING_STATUSES))
    applications = db.scalars(statement).all()
    grouped: dict[str, list[int]] = {}
    buckets = {"0-2_days": 0, "3-7_days": 0, "8-14_days": 0, "15+_days": 0}
    items: list[PendencyItem] = []

    for application in applications:
        waiting_at = application.submitted_at or application.updated_at or application.created_at
        waiting_date = waiting_at.date() if isinstance(waiting_at, datetime) else today
        age = max(0, (today - waiting_date).days)
        if age <= 2:
            buckets["0-2_days"] += 1
        elif age <= 7:
            buckets["3-7_days"] += 1
        elif age <= 14:
            buckets["8-14_days"] += 1
        else:
            buckets["15+_days"] += 1
        grouped.setdefault(application.status, []).append(age)
        items.append(PendencyItem(
            application_id=str(application.id),
            application_number=application.application_number,
            title=application.title,
            status=application.status,
            institution_name=application.institution.name,
            waiting_since=waiting_date,
            days_waiting=age,
        ))

    summaries = [
        PendencyStatusSummary(
            status=key,
            count=len(ages),
            oldest_days=max(ages),
            average_days=round(sum(ages) / len(ages), 1),
        )
        for key, ages in sorted(grouped.items(), key=lambda entry: (-len(entry[1]), entry[0]))
    ]
    items.sort(key=lambda item: (-item.days_waiting, item.waiting_since, item.application_number))
    return PendencyAnalytics(
        as_of=today,
        total_pending=len(items),
        aging_buckets=buckets,
        by_status=summaries,
        oldest_items=items[:10],
    )
