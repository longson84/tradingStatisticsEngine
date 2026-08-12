"""Persistence-neutral contract for current equity listing venues."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class EquityVenueInstrumentRecord:
    instrument_id: int
    symbol: str
    symbol_aliases: tuple[str, ...]
    venue_code: str | None


@dataclass(frozen=True)
class EquityVenueAssignment:
    instrument_id: int
    venue_code: str


class EquityVenueRepository(Protocol):
    def ensure_venue_registry(self) -> None: ...

    def list_us_equity_instruments(
        self,
    ) -> tuple[EquityVenueInstrumentRecord, ...]: ...

    def assign_venues(
        self,
        assignments: tuple[EquityVenueAssignment, ...],
    ) -> int: ...
