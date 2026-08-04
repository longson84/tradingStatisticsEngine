"""Persistence-neutral price-bar repository contract."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol


@dataclass(frozen=True)
class PriceBarRecord:
    ticker: str
    market: str
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
class PriceBarCoverageRecord:
    ticker: str
    first_date: date
    last_date: date


@dataclass(frozen=True)
class PriceBarWriteRecord:
    market: str
    ticker: str
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
class PriceBarStatusRecord:
    universe: str
    market: str
    fetched_at: datetime
    first_date: date
    last_date: date
    symbol_count: int
    row_count: int
    sources: tuple[str, ...]
    price_basis: str


@dataclass(frozen=True)
class PriceBarQuery:
    universe: str
    price_basis: str
    ticker: str | None = None
    start: date | None = None
    end: date | None = None


class PriceBarRepository(Protocol):
    def get_universe_market(self, universe: str) -> str | None: ...

    def get_latest_date(self, universe: str, price_basis: str) -> date | None: ...

    def iter_bars(self, query: PriceBarQuery) -> Iterable[PriceBarRecord]: ...


class PriceBarRefreshRepository(Protocol):
    def get_universe_market(self, universe: str) -> str | None: ...

    def list_coverage(
        self, universe: str, price_basis: str
    ) -> tuple[PriceBarCoverageRecord, ...]: ...

    def upsert_bars(self, records: Iterable[PriceBarWriteRecord]) -> int: ...


class PriceBarMaintenanceRepository(Protocol):
    def get_universe_market(self, universe: str) -> str | None: ...

    def get_status(
        self, universe: str, price_basis: str
    ) -> PriceBarStatusRecord | None: ...

    def list_market_universes(self, market: str) -> tuple[str, ...]: ...

    def delete_market_bars(self, market: str) -> int: ...
