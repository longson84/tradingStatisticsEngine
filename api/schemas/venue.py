"""Public contracts for canonical trading venues."""
from __future__ import annotations

from datetime import time

from pydantic import BaseModel


class VenueResponse(BaseModel):
    id: int
    code: str
    name: str
    venue_type: str
    country_code: str | None = None
    timezone_name: str
    trading_calendar_code: str
    session_cutoff_time: time
    is_active: bool
    source: str
    instrument_count: int
    active_instrument_count: int


class VenueListResponse(BaseModel):
    total: int
    venues: list[VenueResponse]
