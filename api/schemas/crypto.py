"""Public contracts for venue-specific crypto spot markets."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class CryptoMarketInstrumentResponse(BaseModel):
    id: int
    venue_code: str
    venue_name: str
    symbol: str
    base_asset: str
    quote_asset: str
    is_active: bool
    price_tick_size: str | None = None
    quantity_step_size: str | None = None
    minimum_quantity: str | None = None
    minimum_notional: str | None = None
    first_session: date | None = None
    last_session: date | None = None
    stored_sessions: int
    price_source: str | None = None


class CryptoMarketFacetCountResponse(BaseModel):
    value: str
    count: int


class CryptoVenueFacetResponse(BaseModel):
    code: str
    name: str
    count: int


class CryptoMarketFacetsResponse(BaseModel):
    venues: list[CryptoVenueFacetResponse]
    quote_assets: list[CryptoMarketFacetCountResponse]
    active_count: int
    inactive_count: int


class CryptoMarketSummaryResponse(BaseModel):
    instrument_count: int
    active_count: int
    inactive_count: int
    with_history_count: int
    catalog_fetched_at: datetime | None = None


class CryptoMarketListResponse(BaseModel):
    venue_code: str | None = None
    venue_name: str | None = None
    total: int
    offset: int
    limit: int
    instruments: list[CryptoMarketInstrumentResponse]
    facets: CryptoMarketFacetsResponse
    summary: CryptoMarketSummaryResponse
