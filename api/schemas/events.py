"""Request/response schemas for event-analysis endpoints."""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from api.schemas.common import DateRange


class NewLowEpisodesRequest(BaseModel):
    symbols: list[str] = Field(min_length=1)
    date_range: DateRange
    data_source: Literal["yfinance", "vnstock", "csv"] = "yfinance"
    quick_recovery_sessions: int = Field(default=2, ge=0)
    forward_horizons: list[int] = Field(default_factory=lambda: [5, 10, 20, 50, 100, 150, 200])
    lookback_sessions: int = Field(default=50, ge=2)


class NewLowForwardStatsSchema(BaseModel):
    horizon: int
    count: int
    return_percentiles: dict[str, float]
    max_down_percentiles: dict[str, float]


class NewLowEpisodeSchema(BaseModel):
    start_date: date
    start_price: float
    recovery_level: float
    recovered: bool
    recovery_date: date | None
    recovery_sessions: int | None
    ignored_new_lows: int
    low_date: date
    low_price: float
    days_to_low: int
    max_down_pct: float
    forward_returns: dict[str, float | None]
    forward_max_down: dict[str, float | None]


class NewLowCurrentEpisodeSchema(BaseModel):
    start_date: date
    start_price: float
    recovery_level: float
    current_date: date
    current_price: float
    current_down_pct: float
    current_return_pct: float
    max_down_pct: float
    sessions_elapsed: int
    ignored_new_lows: int
    low_date: date
    low_price: float
    days_to_low: int
    recovery_needed_pct: float
    max_down_percentile: float
    ignored_lows_percentile: float
    duration_percentile: float


class NewLowTimeSeriesPointSchema(BaseModel):
    date: date
    close: float
    is_new_low: bool


class NewLowSymbolResultSchema(BaseModel):
    symbol: str
    first_date: date
    last_date: date
    total_bars: int
    latest_price: float
    lookback_sessions: int
    quick_recovery_sessions: int
    raw_new_low_bars: int
    kept_episodes: int
    completed_episodes: int
    active_episodes: int
    quick_ignored_episodes: int
    total_ignored_new_lows: int
    max_down_percentiles: dict[str, float]
    recovery_session_percentiles: dict[str, float]
    ignored_new_low_percentiles: dict[str, float]
    current: NewLowCurrentEpisodeSchema | None
    forward_stats: list[NewLowForwardStatsSchema]
    episodes: list[NewLowEpisodeSchema]
    time_series: list[NewLowTimeSeriesPointSchema]


class NewLowEpisodesResponse(BaseModel):
    results: list[NewLowSymbolResultSchema]
