"""Persistence-neutral read model for canonical trading venues."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from typing import Protocol


@dataclass(frozen=True)
class VenueRecord:
    id: int
    code: str
    name: str
    venue_type: str
    country_code: str | None
    timezone_name: str
    trading_calendar_code: str
    session_cutoff_time: time
    is_active: bool
    source: str
    instrument_count: int
    active_instrument_count: int


class VenueRepository(Protocol):
    def list_venues(self) -> tuple[VenueRecord, ...]: ...
