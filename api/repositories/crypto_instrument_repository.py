"""Persistence-neutral crypto asset and spot-instrument repository contract."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class CryptoAssetWrite:
    code: str
    name: str
    asset_type: str


@dataclass(frozen=True)
class SpotInstrumentWrite:
    symbol: str
    base_asset: str
    quote_asset: str
    is_active: bool
    base_precision: int | None
    quote_precision: int | None
    price_tick_size: Decimal | None
    quantity_step_size: Decimal | None
    minimum_quantity: Decimal | None
    minimum_notional: Decimal | None


@dataclass(frozen=True)
class SpotCatalogWrite:
    venue_code: str
    venue_name: str
    universe_code: str
    universe_name: str
    source: str
    fetched_at: datetime
    assets: tuple[CryptoAssetWrite, ...]
    instruments: tuple[SpotInstrumentWrite, ...]


@dataclass(frozen=True)
class SpotCatalogSyncResult:
    received_instruments: int
    active_instruments: int
    added_instruments: int
    updated_instruments: int
    deactivated_instruments: int
    added_assets: int


@dataclass(frozen=True)
class SpotInstrumentRecord:
    id: int
    symbol: str
    base_asset: str
    quote_asset: str
    first_date: date | None
    last_date: date | None


@dataclass(frozen=True)
class SpotInstrumentListQuery:
    venue_code: str | None = None
    search: str | None = None
    quote_asset: str | None = None
    is_active: bool | None = True
    offset: int = 0
    limit: int = 50


@dataclass(frozen=True)
class SpotInstrumentListRecord:
    id: int
    venue_code: str
    venue_name: str
    symbol: str
    base_asset: str
    quote_asset: str
    is_active: bool
    price_tick_size: Decimal | None
    quantity_step_size: Decimal | None
    minimum_quantity: Decimal | None
    minimum_notional: Decimal | None
    first_date: date | None
    last_date: date | None
    stored_sessions: int
    price_source: str | None


@dataclass(frozen=True)
class SpotInstrumentFacetCount:
    value: str
    count: int


@dataclass(frozen=True)
class SpotInstrumentVenueFacet:
    code: str
    name: str
    count: int


@dataclass(frozen=True)
class SpotInstrumentListFacets:
    venues: tuple[SpotInstrumentVenueFacet, ...]
    quote_assets: tuple[SpotInstrumentFacetCount, ...]
    active_count: int
    inactive_count: int


@dataclass(frozen=True)
class SpotInstrumentSummary:
    instrument_count: int
    active_count: int
    inactive_count: int
    with_history_count: int
    catalog_fetched_at: datetime | None


@dataclass(frozen=True)
class SpotInstrumentListResult:
    total: int
    rows: tuple[SpotInstrumentListRecord, ...]
    facets: SpotInstrumentListFacets
    summary: SpotInstrumentSummary


class CryptoInstrumentRepository(Protocol):
    def sync_spot_catalog(self, catalog: SpotCatalogWrite) -> SpotCatalogSyncResult: ...

    def list_spot_instruments(
        self,
        venue_code: str,
        *,
        symbols: tuple[str, ...] = (),
        quote_assets: tuple[str, ...] = (),
    ) -> tuple[SpotInstrumentRecord, ...]: ...

    def list_spot_catalog(
        self,
        query: SpotInstrumentListQuery,
    ) -> SpotInstrumentListResult: ...
