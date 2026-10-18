"""Persistence-neutral contracts for exact-period session statistics."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Mapping, Protocol

from api.session_statistics import SessionStatisticMetricCode


@dataclass(frozen=True)
class SessionStatisticInstrumentRecord:
    instrument_id: int
    symbol: str
    instrument_type: str
    venue_code: str | None
    currency: str


@dataclass(frozen=True)
class SessionStatisticMetricRecord:
    code: SessionStatisticMetricCode
    value: Decimal


@dataclass(frozen=True)
class SessionStatisticSnapshotWrite:
    instrument_id: int
    period_start: date
    period_end: date
    source: str
    schema_version: int
    fetched_at: datetime
    metrics: Mapping[SessionStatisticMetricCode, Decimal]


@dataclass(frozen=True)
class SessionStatisticSnapshotRecord:
    snapshot_id: int
    instrument_id: int
    period_start: date
    period_end: date
    source: str
    schema_version: int
    fetched_at: datetime
    metrics: tuple[SessionStatisticMetricRecord, ...]


class SessionStatisticsRepository(Protocol):
    def get_instrument(
        self, instrument_id: int
    ) -> SessionStatisticInstrumentRecord | None: ...

    def store_snapshot(self, record: SessionStatisticSnapshotWrite) -> int: ...

    def get_latest_snapshot(
        self, instrument_id: int, period_start: date, period_end: date
    ) -> SessionStatisticSnapshotRecord | None: ...
