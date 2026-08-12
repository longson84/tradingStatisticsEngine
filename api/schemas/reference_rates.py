"""Public contracts for venue-less market reference rates."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class ReferenceRateInstrumentResponse(BaseModel):
    id: int
    symbol: str
    instrument_type: str = "reference_rate"
    base_asset: str
    base_asset_name: str
    quote_asset: str
    quote_asset_name: str
    venue: None = None
    is_active: bool
    catalog_source: str
    first_session: date | None = None
    last_session: date | None = None
    stored_sessions: int
    price_basis: str
    price_source: str | None = None
    price_fetched_at: datetime | None = None


class ReferenceRateFacetCountResponse(BaseModel):
    value: str
    count: int


class ReferenceRateFacetsResponse(BaseModel):
    base_assets: list[ReferenceRateFacetCountResponse]
    quote_assets: list[ReferenceRateFacetCountResponse]
    active_count: int
    inactive_count: int


class ReferenceRateSummaryResponse(BaseModel):
    instrument_count: int
    active_count: int
    inactive_count: int
    with_history_count: int
    earliest_session: date | None = None
    latest_session: date | None = None


class ReferenceRateListResponse(BaseModel):
    total: int
    offset: int
    limit: int
    instruments: list[ReferenceRateInstrumentResponse]
    facets: ReferenceRateFacetsResponse
    summary: ReferenceRateSummaryResponse
