"""Shared market-session calendar helpers for application freshness checks."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from api.venue_calendars import (
    CONTINUOUS_DAILY_CALENDAR,
    US_EQUITY_CALENDAR,
    VN_EQUITY_CALENDAR,
    VenueCalendarMetadata,
)


def latest_completed_venue_session(
    now: datetime,
    schedule: VenueCalendarMetadata,
) -> date:
    """Return the latest daily session complete under one venue schedule."""
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    try:
        timezone = ZoneInfo(schedule.timezone_name)
    except (KeyError, ValueError) as exc:
        raise ValueError(
            f"Unknown venue timezone: {schedule.timezone_name}"
        ) from exc
    local = now.astimezone(timezone)
    if schedule.trading_calendar_code == CONTINUOUS_DAILY_CALENDAR:
        # A continuously traded daily bar is labelled by the UTC date on which
        # it opened and completes at the following day's midnight boundary.
        return local.date() - timedelta(days=1)
    if schedule.trading_calendar_code not in {
        US_EQUITY_CALENDAR,
        VN_EQUITY_CALENDAR,
    }:
        raise ValueError(
            "Unsupported trading calendar: "
            f"{schedule.trading_calendar_code}"
        )
    candidate = (
        local.date()
        if local.time() >= schedule.session_cutoff_time
        else local.date() - timedelta(days=1)
    )
    while candidate.weekday() >= 5:
        candidate -= timedelta(days=1)
    return candidate
