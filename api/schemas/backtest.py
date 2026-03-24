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


class PriceVsMAConfig(BaseModel):
    """Price vs Moving Average strategy.

    Goes long when close > MA, flat otherwise.
    buy_lag / sell_lag: confirmation bars required before entry / exit.
    """
    type: Literal["price_vs_ma"] = "price_vs_ma"
    ma_type: Literal["sma", "ema", "wma"] = "sma"
    ma_length: int = 50
    buy_lag: int = 0
    sell_lag: int = 0


StrategyConfig = BuyAndHoldConfig | PriceVsMAConfig


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


# ---------------------------------------------------------------------------
# Single-ticker analysis request/response
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    symbol: str
    strategy: StrategyConfig
    initial_capital: float = 10_000.0
    data_source: Literal["yfinance", "vnstock", "csv"] = "yfinance"
    start: date | None = None   # defaults to 2000-01-01 in the route
    end: date | None = None     # defaults to today in the route


class PerformanceSummaryResponse(BaseModel):
    total_return_pct: float
    cagr_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    current_drawdown_pct: float
    calmar_ratio: float
    win_rate_pct: float
    avg_win_pct: float
    avg_loss_pct: float
    max_consec_losses: int
    best_trade_pct: float
    worst_trade_pct: float
    total_trades: int
    avg_holding_days: float
    profit_factor: float
    time_in_market_pct: float


class CurrentPositionResponse(BaseModel):
    entry_date: str
    entry_price: float
    holding_days: int
    unrealized_return_pct: float | None
    mae_pct: float | None
    mfe_pct: float | None


class TradeRowResponse(BaseModel):
    symbol: str
    direction: str
    entry_date: str
    exit_date: str | None
    entry_price: float
    exit_price: float | None
    return_pct: float | None
    holding_days: int | None
    mae_pct: float | None
    mfe_pct: float | None
    mae_price: float | None
    mfe_price: float | None
    retracement_pct: float | None


class DistributionRowResponse(BaseModel):
    percentile: int
    value_pct: float
    cumulative_count: int



class MonthlyStatRowResponse(BaseModel):
    label: str
    count: int
    p5: float | None
    p10: float | None
    p15: float | None
    p20: float | None
    p25: float | None
    p50: float | None
    p75: float | None
    p90: float | None
    p95: float | None


class HealthRowResponse(BaseModel):
    year: int
    trades: int
    p5: float | None
    p10: float | None
    p15: float | None
    p20: float | None
    p25: float | None
    p50: float | None
    p75: float | None
    p90: float | None
    p95: float | None


class SingleTickerAnalysisResponse(BaseModel):
    symbol: str
    strategy_label: str
    from_date: str
    to_date: str
    total_bars: int
    current_position: CurrentPositionResponse | None
    strategy: PerformanceSummaryResponse
    bah: PerformanceSummaryResponse
    trades: list[TradeRowResponse]
    return_percentiles: list[DistributionRowResponse]
    mae_percentiles_winners: list[DistributionRowResponse]
    mfe_percentiles_winners: list[DistributionRowResponse]
    monthly_returns_strategy: dict[str, dict[str, float | None]]
    monthly_returns_bah: dict[str, dict[str, float | None]]
    monthly_stats_by_calendar: list[MonthlyStatRowResponse]
    monthly_stats_by_entry_month: list[MonthlyStatRowResponse]
    health_by_year: list[HealthRowResponse]
    equity_curve_strategy: dict[str, float]
    equity_curve_bah: dict[str, float]
