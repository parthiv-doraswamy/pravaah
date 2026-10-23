"""Shared UTC clock helpers for deadlines and scheduled jobs."""

from datetime import UTC, date, datetime


def utc_now() -> datetime:
    """Return the current timezone-aware UTC instant."""
    return datetime.now(UTC)


def utc_today(now: datetime | None = None) -> date:
    """Return the UTC calendar date for an instant (or the current instant).

    Explicit instants must be timezone-aware; silently interpreting a naive
    datetime would make deadline behavior depend on the host machine timezone.
    """
    instant = now if now is not None else utc_now()
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("utc_today requires a timezone-aware datetime")
    return instant.astimezone(UTC).date()
