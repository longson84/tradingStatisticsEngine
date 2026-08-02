"""Request and response schemas for cached market-health analysis."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class MarketHealthWeightsRequest(BaseModel):
    within_10: float = Field(default=0.35, ge=0)
    within_20: float = Field(default=0.30, ge=0)
    within_30: float = Field(default=0.20, ge=0)
    not_below_40: float = Field(default=0.15, ge=0)


class MarketHealthRunRequest(BaseModel):
    weights: MarketHealthWeightsRequest = Field(default_factory=MarketHealthWeightsRequest)
    window: int = Field(default=200, ge=20, le=500)
    minimum_coverage: float = Field(default=0.8, gt=0, le=1)


class MarketHealthPointResponse(BaseModel):
    date: date
    health_score: float
    median_distance: float
    p10_distance: float
    p20_distance: float
    p80_distance: float
    p90_distance: float
    within_10: float
    within_20: float
    within_30: float
    stress_40: float
    coverage_pct: float
    eligible_count: int
    change_5: float | None
    change_20: float | None
    ema_gap: float


class MarketHistoryCacheResponse(BaseModel):
    fetched_at: str
    first_date: date
    last_date: date
    symbol_count: int
    source: str
    price_basis: str


class MarketHealthDistributionBucketResponse(BaseModel):
    label: str
    min_distance: float | None
    max_distance: float | None
    count: int
    percentage: float
    cumulative_percentage: float


class MarketHealthUniverseResponse(BaseModel):
    universe: str
    universe_size: int
    regime: str
    cache: MarketHistoryCacheResponse
    current: MarketHealthPointResponse
    series: list[MarketHealthPointResponse]
    distribution: list[MarketHealthDistributionBucketResponse]


class MarketHealthStockDistanceResponse(BaseModel):
    symbol: str
    date: date
    current_price: float
    rolling_high: float
    distance: float


class MarketHealthDistributionResponse(BaseModel):
    universe: str
    date: date
    window: int
    min_distance: float | None
    max_distance: float | None
    stocks: list[MarketHealthStockDistanceResponse]


class MarketHealthRunResponse(BaseModel):
    window: int
    minimum_coverage: float
    weights: MarketHealthWeightsRequest
    markets: list[MarketHealthUniverseResponse]
