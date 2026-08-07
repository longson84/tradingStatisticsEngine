"""Persistence-neutral price-bar repository contract."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

import pandas as pd


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
class SymbolPriceCoverageRecord:
    ticker: str
    market: str
    first_date: date
    last_date: date
    row_count: int
    source: str
    fetched_at: datetime


@dataclass(frozen=True)
class PriceRefreshStateRecord:
    ticker: str
    market: str
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
    market: str
    ticker: str
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
    expected_session: date | None = None
    coverage_through: date | None = None
    universe_symbol_count: int = 0
    current_symbol_count: int = 0
    stale_symbol_count: int = 0
    missing_symbol_count: int = 0
    checked_no_new_bar_count: int = 0
    failed_refresh_symbol_count: int = 0


@dataclass(frozen=True)
class PriceBarQuery:
    universe: str
    price_basis: str
    ticker: str | None = None
    start: date | None = None
    end: date | None = None


@dataclass(frozen=True)
class SymbolPriceBarQuery:
    market: str
    ticker: str
    price_basis: str
    start: date | None = None
    end: date | None = None


@dataclass(frozen=True)
class SymbolSetPriceBarQuery:
    market: str
    tickers: tuple[str, ...]
    price_basis: str
    start: date | None = None
    end: date | None = None


class PriceBarRepository(Protocol):
    def get_universe_market(self, universe: str) -> str | None: ...

    def get_latest_date(self, universe: str, price_basis: str) -> date | None: ...

    def iter_bars(self, query: PriceBarQuery) -> Iterable[PriceBarRecord]: ...

    def instrument_exists(self, market: str, ticker: str) -> bool: ...

    def get_symbol_coverage(
        self, market: str, ticker: str, price_basis: str
    ) -> SymbolPriceCoverageRecord | None: ...

    def iter_symbol_bars(
        self, query: SymbolPriceBarQuery
    ) -> Iterable[PriceBarRecord]: ...

    def list_symbol_coverages(
        self, market: str, tickers: tuple[str, ...], price_basis: str
    ) -> tuple[SymbolPriceCoverageRecord, ...]: ...

    def list_refresh_states(
        self, market: str, tickers: tuple[str, ...], price_basis: str
    ) -> tuple[PriceRefreshStateRecord, ...]: ...

    def iter_symbol_set_bars(
        self, query: SymbolSetPriceBarQuery
    ) -> Iterable[PriceBarRecord]: ...

    def upsert_bars(self, records: Iterable[PriceBarWriteRecord]) -> int: ...

    def upsert_refresh_states(
        self, records: Iterable[PriceRefreshStateWriteRecord]
    ) -> int: ...

class PriceBarRefreshRepository(Protocol):
    def get_universe_market(self, universe: str) -> str | None: ...

    def list_symbol_coverages(
        self, market: str, tickers: tuple[str, ...], price_basis: str
    ) -> tuple[SymbolPriceCoverageRecord, ...]: ...

    def list_refresh_states(
        self, market: str, tickers: tuple[str, ...], price_basis: str
    ) -> tuple[PriceRefreshStateRecord, ...]: ...

    def upsert_bars(self, records: Iterable[PriceBarWriteRecord]) -> int: ...

    def upsert_refresh_states(
        self, records: Iterable[PriceRefreshStateWriteRecord]
    ) -> int: ...


class MarketHealthRepository(Protocol):
    def get_universe_market(self, universe: str) -> str | None: ...

    def get_latest_date(self, universe: str, price_basis: str) -> date | None: ...

    def load_close_matrix(self, query: PriceBarQuery) -> pd.DataFrame: ...

    def get_status(
        self, universe: str, price_basis: str, expected_session: date
    ) -> PriceBarStatusRecord | None: ...


class PriceBarMaintenanceRepository(Protocol):
    def get_universe_market(self, universe: str) -> str | None: ...

    def get_status(
        self, universe: str, price_basis: str, expected_session: date
    ) -> PriceBarStatusRecord | None: ...

    def list_market_universes(self, market: str) -> tuple[str, ...]: ...

    def delete_market_bars(self, market: str) -> int: ...
