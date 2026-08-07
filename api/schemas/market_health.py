"""Request and response schemas for cached market-health analysis."""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


MarketHealthUniverse = Literal[
    "US500", "US2000", "US100",
    "VNALL", "VN100", "VN30", "VNMID", "VNSML",
]


class MarketHealthRunRequest(BaseModel):
    window: int = Field(default=200, ge=20, le=500)
    minimum_coverage: float = Field(default=0.8, gt=0, le=1)
    universes: list[MarketHealthUniverse] = Field(
        default_factory=lambda: [
            "US500", "US2000", "US100",
            "VNALL", "VN100", "VN30", "VNMID", "VNSML",
        ],
        min_length=1,
        max_length=8,
    )


class MarketHealthPointResponse(BaseModel):
    date: date
    median_distance: float
    coverage_pct: float
    eligible_count: int


class MarketHealthSeriesPointResponse(BaseModel):
    date: date
    median_distance: float


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
    universe: MarketHealthUniverse
    universe_size: int
    cache: MarketHistoryCacheResponse
    current: MarketHealthPointResponse
    series: list[MarketHealthSeriesPointResponse]
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
    markets: list[MarketHealthUniverseResponse]
