"""Persistence-neutral close-only query contract for Universe statistics."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable, Protocol


@dataclass(frozen=True)
class UniverseStatsCloseQuery:
    instrument_price_bases: tuple[tuple[int, str], ...]
    start: date
    end: date


@dataclass(frozen=True)
class UniverseStatsCloseRecord:
    instrument_id: int
    trading_date: date
    close: float
    source: str
    fetched_at: datetime


class UniverseStatsRepository(Protocol):
    def iter_closes(
        self, query: UniverseStatsCloseQuery
    ) -> Iterable[UniverseStatsCloseRecord]: ...
