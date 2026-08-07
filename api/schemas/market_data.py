"""Request and response models for local market-history cache management."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


MarketUniverse = Literal[
    "US500", "US2000", "US100",
    "VNALL", "VN100", "VN30", "VNMID", "VNSML",
]


class MarketDataJobResponse(BaseModel):
    id: str
    market: MarketUniverse
    mode: Literal["incremental", "full"]
    dataset: Literal["prices", "fundamentals"] = "prices"
    status: Literal["queued", "running", "completed", "failed"]
    current: int
    total: int
    message: str
    started_at: str | None
    finished_at: str | None
    error: str | None


class MarketDataCacheStatus(BaseModel):
    universe: MarketUniverse
    exists: bool
    fetched_at: str | None = None
    recent_activity_at: str | None = None
    first_date: str | None = None
    last_date: str | None = None
    expected_session: str | None = None
    coverage_through: str | None = None
    symbol_count: int | None = None
    universe_symbol_count: int = 0
    current_symbol_count: int = 0
    stale_symbol_count: int = 0
    missing_symbol_count: int = 0
    checked_no_new_bar_count: int = 0
    failed_refresh_symbol_count: int = 0
    row_count: int | None = None
    source: str | None = None
    price_basis: str | None = None
    errors: list[dict[str, str]] = Field(default_factory=list)
    latest_job: MarketDataJobResponse | None = None
    fundamentals_exists: bool = False
    fundamentals_fetched_at: str | None = None
    fundamentals_recent_activity_at: str | None = None
    fundamentals_oldest_fetched_at: str | None = None
    fundamentals_symbol_count: int = 0
    fundamentals_snapshot_count: int = 0
    latest_fundamentals_job: MarketDataJobResponse | None = None


class MarketDataStatusResponse(BaseModel):
    price_storage: Literal["PostgreSQL"]
    fundamentals_storage: Literal["PostgreSQL"]
    markets: list[MarketDataCacheStatus]


class MarketDataClearResponse(BaseModel):
    requested_universe: MarketUniverse
    market: Literal["US", "VN"]
    affected_universes: list[MarketUniverse]
    deleted_rows: int
    cleared: bool


class SymbolPricePointResponse(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None
    eps_ttm: float | None = None
    shares_outstanding: float | None = None
    trailing_pe: float | None = None
    trailing_pb: float | None = None
    relative_strength: float | None = None


class SymbolPriceHistoryResponse(BaseModel):
    symbol: str
    universe: MarketUniverse
    source: str
    price_basis: str
    fetched_at: str
    first_date: str
    last_date: str
    row_count: int
    relative_strength_benchmark: Literal["VN30", "SPX"]
    trailing_pe_source: str | None = None
    trailing_pe_method: str | None = None
    trailing_pe_fetched_at: str | None = None
    fundamentals_fields: list[str] = Field(default_factory=list)
    provider_reported_pe: float | None = None
    provider_reported_pb: float | None = None
    provider_ratio_effective_date: str | None = None
    provider_ratio_period: str | None = None
    shares_growth_pct: float | None = None
    shares_growth_cagr_pct: float | None = None
    shares_growth_observed_years: float | None = None
    shares_growth_start_date: str | None = None
    shares_growth_full_10y: bool = False
    shares_cagr_5y_pct: float | None = None
    shares_cagr_5y_observed_years: float | None = None
    shares_cagr_5y_start_date: str | None = None
    shares_cagr_full_5y: bool = False
    prices: list[SymbolPricePointResponse]
