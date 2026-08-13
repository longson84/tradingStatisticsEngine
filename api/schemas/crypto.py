"""Public contracts for venue-specific crypto spot instruments."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class CryptoInstrumentResponse(BaseModel):
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


class CryptoInstrumentFacetCountResponse(BaseModel):
    value: str
    count: int


class CryptoVenueFacetResponse(BaseModel):
    code: str
    name: str
    count: int


class CryptoInstrumentFacetsResponse(BaseModel):
    venues: list[CryptoVenueFacetResponse]
    quote_assets: list[CryptoInstrumentFacetCountResponse]
    active_count: int
    inactive_count: int


class CryptoInstrumentSummaryResponse(BaseModel):
    instrument_count: int
    active_count: int
    inactive_count: int
    with_history_count: int
    catalog_fetched_at: datetime | None = None


class CryptoInstrumentListResponse(BaseModel):
    venue_code: str | None = None
    venue_name: str | None = None
    total: int
    offset: int
    limit: int
    instruments: list[CryptoInstrumentResponse]
    facets: CryptoInstrumentFacetsResponse
    summary: CryptoInstrumentSummaryResponse
