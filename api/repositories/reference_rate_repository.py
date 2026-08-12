"""Persistence-neutral reference-rate instrument repository contract."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol


REFERENCE_RATE_PRICE_BASIS = "provider_unspecified"


@dataclass(frozen=True)
class ReferenceRateWrite:
    symbol: str
    base_asset: str
    base_asset_name: str
    base_asset_type: str
    quote_asset: str
    quote_asset_name: str
    quote_asset_type: str
    source: str


@dataclass(frozen=True)
class ReferenceRateInstrumentRecord:
    id: int
    symbol: str
    base_asset: str
    base_asset_name: str
    quote_asset: str
    quote_asset_name: str
    is_active: bool
    catalog_source: str
    first_date: date | None
    last_date: date | None
    stored_sessions: int
    price_source: str | None
    price_fetched_at: datetime | None


@dataclass(frozen=True)
class ReferenceRateListQuery:
    search: str | None = None
    base_asset: str | None = None
    quote_asset: str | None = None
    is_active: bool | None = True
    offset: int = 0
    limit: int = 50


@dataclass(frozen=True)
class ReferenceRateFacetCount:
    value: str
    count: int


@dataclass(frozen=True)
class ReferenceRateListFacets:
    base_assets: tuple[ReferenceRateFacetCount, ...]
    quote_assets: tuple[ReferenceRateFacetCount, ...]
    active_count: int
    inactive_count: int


@dataclass(frozen=True)
class ReferenceRateSummary:
    instrument_count: int
    active_count: int
    inactive_count: int
    with_history_count: int
    earliest_session: date | None
    latest_session: date | None


@dataclass(frozen=True)
class ReferenceRateListResult:
    total: int
    rows: tuple[ReferenceRateInstrumentRecord, ...]
    facets: ReferenceRateListFacets
    summary: ReferenceRateSummary


class ReferenceRateRepository(Protocol):
    def upsert_reference_rate(
        self, value: ReferenceRateWrite
    ) -> ReferenceRateInstrumentRecord: ...

    def get_reference_rate(
        self, symbol: str
    ) -> ReferenceRateInstrumentRecord | None: ...

    def list_reference_rates(
        self, query: ReferenceRateListQuery
    ) -> ReferenceRateListResult: ...
