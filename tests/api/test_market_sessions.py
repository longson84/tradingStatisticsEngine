from __future__ import annotations

from datetime import UTC, date, datetime, time

import pytest

from api.market_sessions import (
    latest_completed_venue_session,
)
from api.venue_calendars import VenueCalendarMetadata, venue_calendar


def test_equity_venue_calendar_respects_session_cutoff():
    now = datetime(2026, 8, 3, 20, 14, tzinfo=UTC)
    assert latest_completed_venue_session(
        now,
        venue_calendar("NYSE"),
    ) == date(2026, 7, 31)
    assert latest_completed_venue_session(
        datetime(2026, 8, 3, 20, 15, tzinfo=UTC),
        venue_calendar("NASDAQ"),
    ) == date(2026, 8, 3)


def test_vietnam_and_continuous_venue_schedules_have_distinct_day_rules():
    assert latest_completed_venue_session(
        datetime(2026, 8, 3, 9, tzinfo=UTC),
        venue_calendar("HOSE"),
    ) == date(2026, 8, 3)
    assert latest_completed_venue_session(
        datetime(2026, 8, 3, 12, tzinfo=UTC),
        venue_calendar("BINANCE_SPOT"),
    ) == date(2026, 8, 2)


def test_venue_session_helper_rejects_invalid_timezone_and_calendar():
    with pytest.raises(ValueError, match="Unknown venue timezone"):
        latest_completed_venue_session(
            datetime(2026, 8, 3, tzinfo=UTC),
            VenueCalendarMetadata("Not/AZone", "US_EQUITIES", time(16, 15)),
        )
    with pytest.raises(ValueError, match="Unsupported trading calendar"):
        latest_completed_venue_session(
            datetime(2026, 8, 3, tzinfo=UTC),
            VenueCalendarMetadata("UTC", "UNKNOWN", time(0, 0)),
        )
