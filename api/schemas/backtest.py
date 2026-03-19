"""Request/response schemas for /backtest and /sweep endpoints."""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, model_validator

from api.schemas.common import DateRange, TradeSchema


# ---------------------------------------------------------------------------
# Strategy configuration — discriminated union by "type"
# ---------------------------------------------------------------------------

class BuyAndHoldConfig(BaseModel):
    type: Literal["buy_and_hold"] = "buy_and_hold"
    weight: float = 1.0


class MACrossoverConfig(BaseModel):
    type: Literal["ma_crossover"] = "ma_crossover"
    fast_period: int = 10
    slow_period: int = 50
    ma_type: Literal["sma", "ema", "wma"] = "sma"


StrategyConfig = BuyAndHoldConfig | MACrossoverConfig


# ---------------------------------------------------------------------------
# Backtest request
# ---------------------------------------------------------------------------

class BacktestRequest(BaseModel):
    symbols: list[str]
    date_range: DateRange
    strategy: StrategyConfig
    initial_capital: float = 10_000.0
    max_leverage: float = 1.0
    data_source: Literal["yfinance", "vnstock", "csv"] = "yfinance"

    @model_validator(mode="after")
    def check_symbols_non_empty(self) -> "BacktestRequest":
        if not self.symbols:
            raise ValueError("symbols must not be empty")
        return self


# ---------------------------------------------------------------------------
# Backtest response
# ---------------------------------------------------------------------------

class PortfolioResultResponse(BaseModel):
    equity_curve: dict[str, float]            # ISO date str → NAV value
    trades: list[TradeSchema]
    weights: dict[str, dict[str, float]]      # symbol → {ISO date str → weight}
    total_return_pct: float
    final_nav: float


# ---------------------------------------------------------------------------
# Sweep (multi-config comparison) request/response
# ---------------------------------------------------------------------------

class SweepRequest(BaseModel):
    symbols: list[str]
    date_range: DateRange
    strategies: list[StrategyConfig]
    initial_capital: float = 10_000.0
    max_leverage: float = 1.0
    data_source: Literal["yfinance", "vnstock", "csv"] = "yfinance"
    max_workers: int = 4

    @model_validator(mode="after")
    def check_strategies_non_empty(self) -> "SweepRequest":
        if not self.strategies:
            raise ValueError("strategies must not be empty")
        return self


class SweepResultItem(BaseModel):
    strategy_type: str
    equity_curve: dict[str, float]
    total_return_pct: float
    final_nav: float
    trade_count: int


class SweepErrorItem(BaseModel):
    strategy_type: str
    error: str


class SweepResponse(BaseModel):
    results: list[SweepResultItem]
    errors: list[SweepErrorItem]
