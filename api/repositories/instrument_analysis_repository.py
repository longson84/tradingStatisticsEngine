"""Persistence-neutral instrument discovery and analysis-price contract."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable, Protocol

from api.repositories.price_bar_repository import PriceBarRecord


US_EQUITY_PRICE_BASIS = "adjusted"
DEFAULT_CANONICAL_PRICE_BASIS = "provider_unspecified"
SPOT_PRICE_BASIS = "venue_unadjusted"
MARKET_INDEX_PRICE_BASIS = "index_level"


@dataclass(frozen=True)
class AnalysisInstrumentQuery:
    scope: str | None = None
    universe: str | None = None
    search: str | None = None
    sector: str | None = None
    industry: str | None = None
    venue_code: str | None = None
    has_price_history: bool = True
    offset: int = 0
    limit: int = 20


@dataclass(frozen=True)
class AnalysisInstrumentRecord:
    id: int
    symbol: str
    instrument_type: str
    company_id: int | None
    company_name: str | None
    sector: str | None
    industry: str | None
    venue_code: str | None
    venue_name: str | None
    base_asset: str | None
    quote_asset: str | None
    currency: str
    price_basis: str
    price_source: str | None
    first_date: date | None
    last_date: date | None
    stored_sessions: int
    universes: tuple[str, ...]


@dataclass(frozen=True)
class AnalysisInstrumentFacetCount:
    value: str
    count: int


@dataclass(frozen=True)
class AnalysisInstrumentFacets:
    all_count: int
    sectors: tuple[AnalysisInstrumentFacetCount, ...]


@dataclass(frozen=True)
class AnalysisInstrumentListResult:
    rows: tuple[AnalysisInstrumentRecord, ...]
    total: int
    facets: AnalysisInstrumentFacets


@dataclass(frozen=True)
class AnalysisInstrumentPriceBarRecord:
    instrument_id: int
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


class InstrumentAnalysisRepository(Protocol):
    def list_instruments(
        self, query: AnalysisInstrumentQuery
    ) -> AnalysisInstrumentListResult: ...

    def get_instrument(self, instrument_id: int) -> AnalysisInstrumentRecord | None: ...

    def get_market_index(self, code: str) -> AnalysisInstrumentRecord | None: ...

    def get_instruments(
        self, instrument_ids: tuple[int, ...]
    ) -> tuple[AnalysisInstrumentRecord, ...]: ...

    def iter_price_bars(
        self, instrument_id: int, price_basis: str
    ) -> Iterable[PriceBarRecord]: ...

    def iter_instrument_set_price_bars(
        self, instrument_ids: tuple[int, ...]
    ) -> Iterable[AnalysisInstrumentPriceBarRecord]: ...
