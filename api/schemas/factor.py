"""Request/response schemas for /factors endpoints."""
from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel

from api.schemas.common import DateRange
from trading_engine.constants import DEFAULT_QR_DAYS, DEFAULT_RARITY_ZONES


class FactorRequest(BaseModel):
    symbol: str
    date_range: DateRange
    factor_type: Literal["moving_average", "bollinger", "donchian", "distance_from_peak"]
    # MA-specific
    period: int = 20
    ma_type: Literal["sma", "ema", "wma"] = "sma"
    # Bollinger-specific
    std_dev: float = 2.0
    data_source: Literal["yfinance", "vnstock", "csv"] = "yfinance"


class FactorAnalysisResponse(BaseModel):
    factor_name: str
    current_value: float
    current_percentile: float
    history_length_days: int
    percentiles: dict[str, float]   # "p10", "p25", "p50", "p75", "p90" → value


class CrossSectionalRequest(BaseModel):
    symbols: list[str]
    date_range: DateRange
    factor_type: Literal["moving_average", "bollinger", "donchian", "distance_from_peak"]
    period: int = 20
    ma_type: Literal["sma", "ema", "wma"] = "sma"
    threshold: float = 0.0
    data_source: Literal["yfinance", "vnstock", "csv"] = "yfinance"


class CrossSectionalResponse(BaseModel):
    factor_name: str
    universe: list[str]
    breadth: dict[str, float]           # ISO date → breadth value [0, 1]
    pct_above: dict[str, float]         # ISO date → % above threshold
    universe_median: dict[str, float]   # ISO date → median factor value


class RegimeRequest(BaseModel):
    symbols: list[str]
    date_range: DateRange
    factor_type: Literal["moving_average", "bollinger", "donchian", "distance_from_peak"]
    period: int = 20
    ma_type: Literal["sma", "ema", "wma"] = "sma"
    threshold: float = 0.0
    lower_threshold: float = 0.4
    upper_threshold: float = 0.6
    data_source: Literal["yfinance", "vnstock", "csv"] = "yfinance"


class RegimeResponse(BaseModel):
    labels: dict[str, str]      # ISO date → "risk_on" | "risk_off" | "transition"
    breadth: dict[str, float]   # ISO date → breadth value


# ── Rarity Analysis ──────────────────────────────────────────────────────────

class RarityRequest(BaseModel):
    symbol: str
    date_range: DateRange
    factor_type: Literal["moving_average", "bollinger", "donchian", "distance_from_peak"]
    period: int = 200
    ma_type: Literal["sma", "ema", "wma"] = "sma"
    std_dev: float = 2.0
    data_source: Literal["yfinance", "vnstock", "csv"] = "yfinance"
    zones: list[int] = DEFAULT_RARITY_ZONES
    quick_recovery_days: int = DEFAULT_QR_DAYS


class ZoneStatsSchema(BaseModel):
    zone_pct: int
    threshold_value: float
    count: int
    qr_count: int
    qr_pct: float
    count_5y: int
    qr_5y: int
    count_10y: int
    qr_10y: int
    avg_days: float
    mmae_pct: float
    mae_by_percentile: dict[str, float]   # "80" → value, "85" → value, ...
    is_current_zone: bool


class ZoneEntrySchema(BaseModel):
    zone_pct: int
    start_date: date
    entry_price: float
    entry_factor: float
    low_price: float
    low_date: date
    low_factor: float
    mae_pct: float
    days_to_low: int
    recovery_date: date | None
    days_to_recovery: int | None
    is_active: bool
    is_quick_recovery: bool
    level: int
    children_count: int
    parent_zone_pct: int | None
    parent_start_date: date | None


class RarityAnalysisResponse(BaseModel):
    factor_name: str
    symbol: str
    stats_date: date
    first_date: date
    last_date: date
    total_bars: int
    current_price: float
    current_value: float
    current_percentile: float
    current_zone: int | None
    zone_entry_date: date | None
    zone_entry_price: float | None
    sessions_in_zone: int
    max_potential_drop_pct: float
    factor_context: dict[str, Any]
    zone_stats: list[ZoneStatsSchema]
    entries: list[ZoneEntrySchema]
