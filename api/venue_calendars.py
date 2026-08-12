"""Canonical daily-session metadata for economic trading venues."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import time


US_EQUITY_CALENDAR = "US_EQUITIES"
VN_EQUITY_CALENDAR = "VN_EQUITIES"
CONTINUOUS_DAILY_CALENDAR = "CRYPTO_24_7"


@dataclass(frozen=True)
class VenueCalendarMetadata:
    timezone_name: str
    trading_calendar_code: str
    session_cutoff_time: time


_US_EQUITY = VenueCalendarMetadata(
    timezone_name="America/New_York",
    trading_calendar_code=US_EQUITY_CALENDAR,
    session_cutoff_time=time(16, 15),
)
_VN_EQUITY = VenueCalendarMetadata(
    timezone_name="Asia/Ho_Chi_Minh",
    trading_calendar_code=VN_EQUITY_CALENDAR,
    session_cutoff_time=time(15, 15),
)


VENUE_CALENDARS = {
    "NASDAQ": _US_EQUITY,
    "NYSE": _US_EQUITY,
    "NYSE_AMERICAN": _US_EQUITY,
    "NYSE_ARCA": _US_EQUITY,
    "CBOE_BZX": _US_EQUITY,
    "IEX": _US_EQUITY,
    "HOSE": _VN_EQUITY,
    "HNX": _VN_EQUITY,
    "UPCOM": _VN_EQUITY,
    "BINANCE_SPOT": VenueCalendarMetadata(
        timezone_name="UTC",
        trading_calendar_code=CONTINUOUS_DAILY_CALENDAR,
        session_cutoff_time=time(0, 0),
    ),
}


def venue_calendar(venue_code: str) -> VenueCalendarMetadata:
    try:
        return VENUE_CALENDARS[venue_code.upper().strip()]
    except KeyError as exc:
        raise ValueError(f"No trading calendar registered for venue {venue_code}") from exc
