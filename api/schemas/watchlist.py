"""Public watchlist API contracts."""
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class WatchlistCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    instrument_ids: list[int] = Field(default_factory=list, max_length=5000)


class WatchlistUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    instrument_ids: list[int] = Field(default_factory=list, max_length=5000)


class WatchlistMemberResponse(BaseModel):
    instrument_id: int
    symbol: str
    instrument_type: str
    company_id: int | None = None
    company_name: str | None = None
    sector: str | None = None
    industry: str | None = None
    venue_code: str | None = None
    venue_name: str | None = None
    base_asset: str | None = None
    quote_asset: str | None = None
    currency: str
    position: int


class WatchlistSummaryResponse(BaseModel):
    id: int
    name: str
    description: str
    member_count: int
    instrument_types: list[str]
    equity_count: int
    crypto_spot_count: int
    reference_rate_count: int
    market_index_count: int
    created_at: datetime
    updated_at: datetime


class WatchlistResponse(WatchlistSummaryResponse):
    members: list[WatchlistMemberResponse]


class WatchlistListResponse(BaseModel):
    watchlists: list[WatchlistSummaryResponse]


class WatchlistDeleteResponse(BaseModel):
    id: int
    deleted: bool
