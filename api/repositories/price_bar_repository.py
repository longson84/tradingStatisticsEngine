"""Persistence-neutral price-bar repository contract."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

@dataclass(frozen=True)
class PriceBarRecord:
    symbol: str
    trading_date: date
    open: float
    high: float
    low: float
    close: float
    volume: float | None
    currency: str
    price_scale: int
    price_basis: str
    source: str
    fetched_at: datetime


@dataclass(frozen=True)
class SymbolPriceCoverageRecord:
    instrument_id: int
    symbol: str
    first_date: date
    last_date: date
    row_count: int
    source: str
    fetched_at: datetime


@dataclass(frozen=True)
class PriceRefreshStateRecord:
    instrument_id: int
    symbol: str
    price_basis: str
    attempted_through: date
    returned_through: date | None
    outcome: str
    primary_source: str
    selected_source: str | None
    detail: str | None
    attempted_at: datetime


@dataclass(frozen=True)
class PriceRefreshStateWriteRecord:
    instrument_id: int
    price_basis: str
    attempted_through: date
    returned_through: date | None
    outcome: str
    primary_source: str
    selected_source: str | None
    detail: str | None
    attempted_at: datetime


@dataclass(frozen=True)
class PriceBarWriteRecord:
    instrument_id: int
    trading_date: date
    open: float
    high: float
    low: float
    close: float
    volume: float | None
    currency: str
    price_scale: int
    price_basis: str
    source: str
    fetched_at: datetime


@dataclass(frozen=True)
class PriceInstrumentRecord:
    instrument_id: int
    symbol: str
    currency: str
    instrument_type: str
    venue_code: str | None


@dataclass(frozen=True)
class InstrumentPriceBarQuery:
    instrument_id: int
    price_basis: str
    start: date | None = None
    end: date | None = None


class PriceBarRepository(Protocol):
    def get_instrument(
        self, instrument_id: int
    ) -> PriceInstrumentRecord | None: ...

    def get_instrument_coverage(
        self, instrument_id: int, price_basis: str
    ) -> SymbolPriceCoverageRecord | None: ...

    def list_instrument_coverages(
        self, instrument_ids: tuple[int, ...], price_basis: str
    ) -> tuple[SymbolPriceCoverageRecord, ...]: ...

    def list_instrument_refresh_states(
        self, instrument_ids: tuple[int, ...], price_basis: str
    ) -> tuple[PriceRefreshStateRecord, ...]: ...

    def iter_instrument_bars(
        self, query: InstrumentPriceBarQuery
    ) -> Iterable[PriceBarRecord]: ...

    def upsert_bars(self, records: Iterable[PriceBarWriteRecord]) -> int: ...

    def upsert_refresh_states(
        self, records: Iterable[PriceRefreshStateWriteRecord]
    ) -> int: ...


class PriceBarRefreshRepository(Protocol):
    def list_instrument_coverages(
        self, instrument_ids: tuple[int, ...], price_basis: str
    ) -> tuple[SymbolPriceCoverageRecord, ...]: ...

    def list_instrument_refresh_states(
        self, instrument_ids: tuple[int, ...], price_basis: str
    ) -> tuple[PriceRefreshStateRecord, ...]: ...

    def upsert_bars(self, records: Iterable[PriceBarWriteRecord]) -> int: ...

    def upsert_refresh_states(
        self, records: Iterable[PriceRefreshStateWriteRecord]
    ) -> int: ...
