"""Public watchlist API contracts."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


MarketCode = Literal["US", "VN"]


class WatchlistCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    market: MarketCode
    description: str = Field(default="", max_length=500)
    tickers: list[str] = Field(default_factory=list, max_length=5000)


class WatchlistUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    tickers: list[str] = Field(default_factory=list, max_length=5000)


class WatchlistMemberResponse(BaseModel):
    ticker: str
    company_name: str
    market: MarketCode
    sector: str | None = None
    industry: str | None = None
    exchange: str | None = None
    position: int


class WatchlistSummaryResponse(BaseModel):
    id: int
    name: str
    market: MarketCode
    description: str
    member_count: int
    created_at: datetime
    updated_at: datetime


class WatchlistResponse(BaseModel):
    id: int
    name: str
    market: MarketCode
    description: str
    member_count: int
    created_at: datetime
    updated_at: datetime
    members: list[WatchlistMemberResponse]


class WatchlistListResponse(BaseModel):
    watchlists: list[WatchlistSummaryResponse]


class WatchlistDeleteResponse(BaseModel):
    id: int
    deleted: bool


class WatchlistRefreshJobResponse(BaseModel):
    id: str
    watchlist_id: int
    watchlist_name: str
    market: MarketCode
    status: Literal["queued", "running", "completed", "failed"]
    current: int
    total: int
    message: str
    started_at: str | None
    finished_at: str | None
    error: str | None


class WatchlistRefreshJobsResponse(BaseModel):
    jobs: list[WatchlistRefreshJobResponse]
