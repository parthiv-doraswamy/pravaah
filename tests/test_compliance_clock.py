"""Regression tests for UTC calendar-date and expiry classification consistency."""

from datetime import UTC, date, datetime, timedelta

import pytest

from app.core.clock import utc_today
from app.services.notification_jobs import expiry_severity


def test_utc_today_uses_utc_date_across_local_midnight():
    # This instant is already the next calendar day in UTC, regardless of host TZ.
    instant = datetime(2026, 10, 23, 0, 15, tzinfo=UTC)
    assert utc_today(instant) == date(2026, 10, 23)


def test_utc_today_normalizes_aware_non_utc_instants():
    # 00:30 at UTC+05:30 is still the previous day in UTC.
    from datetime import timezone

    instant = datetime(2026, 10, 23, 0, 30, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    assert utc_today(instant) == date(2026, 10, 22)


def test_utc_today_rejects_naive_datetimes():
    with pytest.raises(ValueError, match="timezone-aware"):
        utc_today(datetime(2026, 10, 23, 0, 15))


@pytest.mark.parametrize(
    ("days", "expected"),
    [
        (-2, ("expired", -2)),
        (-1, ("expired", -1)),
        (0, ("urgent", 0)),
        (1, ("urgent", 1)),
        (2, ("warning", 2)),
        (7, ("warning", 7)),
        (8, ("upcoming", 8)),
        (30, ("upcoming", 30)),
        (31, None),
    ],
)
def test_expiry_severity_boundaries(days, expected):
    today = date(2026, 10, 23)
    assert expiry_severity(today + timedelta(days=days), today) == expected
