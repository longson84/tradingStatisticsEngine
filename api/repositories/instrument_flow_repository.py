"""Persistence-neutral contracts for canonical Instrument participant flows."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Protocol


ParticipantType = Literal["foreign", "proprietary"]


@dataclass(frozen=True)
class FlowInstrumentRecord:
    instrument_id: int
    symbol: str
    instrument_type: str
    venue_code: str | None
    currency: str


@dataclass(frozen=True)
class InstrumentFlowRecord:
    instrument_id: int
    trading_date: date
    participant_type: ParticipantType
    buy_volume: Decimal
    buy_value: Decimal
    sell_volume: Decimal
    sell_value: Decimal
    net_volume: Decimal
    net_value: Decimal
    currency: str
    source: str
    fetched_at: datetime


@dataclass(frozen=True)
class InstrumentFlowWriteRecord:
    instrument_id: int
    trading_date: date
    participant_type: ParticipantType
    buy_volume: Decimal
    buy_value: Decimal
    sell_volume: Decimal
    sell_value: Decimal
    net_volume: Decimal
    net_value: Decimal
    currency: str
    source: str
    fetched_at: datetime


@dataclass(frozen=True)
class InstrumentFlowCoverageRecord:
    instrument_id: int
    participant_type: ParticipantType
    first_date: date
    last_date: date
    row_count: int
    source: str
    fetched_at: datetime


@dataclass(frozen=True)
class InstrumentFlowQuery:
    instrument_id: int
    participant_type: ParticipantType
    start: date | None = None
    end: date | None = None


class InstrumentFlowRepository(Protocol):
    def get_instrument(self, instrument_id: int) -> FlowInstrumentRecord | None: ...

    def get_coverage(
        self, instrument_id: int, participant_type: ParticipantType
    ) -> InstrumentFlowCoverageRecord | None: ...

    def iter_observations(
        self, query: InstrumentFlowQuery
    ) -> Iterable[InstrumentFlowRecord]: ...

    def upsert_observations(
        self, records: Iterable[InstrumentFlowWriteRecord]
    ) -> int: ...
