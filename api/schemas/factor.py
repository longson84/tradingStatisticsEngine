"""Request/response schemas for /factors endpoints."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from api.schemas.common import DateRange


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
