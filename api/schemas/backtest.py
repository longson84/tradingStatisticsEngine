"""Request/response schemas for exact-instrument strategy analysis."""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, model_validator

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
# Single-ticker analysis request/response
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    instrument_id: int
    strategy: StrategyConfig
    initial_capital: float = 10_000.0
    start: date | None = None
    end: date | None = None

    @model_validator(mode="after")
    def check_date_order(self) -> "AnalyzeRequest":
        if self.start is not None and self.end is not None and self.start > self.end:
            raise ValueError("start must not be after end")
        return self


class PerformanceSummaryResponse(BaseModel):
    total_return_pct: float
    cagr_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    current_drawdown_pct: float
    current_drawdown_days: int
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
    early_returns: dict[str, float | None] = {}


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


class UndercutDistributionRowResponse(BaseModel):
    undercuts: int
    trade_count: int
    pct_of_winners: float


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
    mfe_percentiles_losers: list[DistributionRowResponse]
    monthly_returns_strategy: dict[str, dict[str, float | None]]
    monthly_returns_bah: dict[str, dict[str, float | None]]
    monthly_stats_by_calendar: list[MonthlyStatRowResponse]
    monthly_stats_by_entry_month: list[MonthlyStatRowResponse]
    health_by_year: list[HealthRowResponse]
    equity_curve_strategy: dict[str, float]
    equity_curve_bah: dict[str, float]
    ticker_prices: dict[str, float]
    undercut_distribution: list[UndercutDistributionRowResponse] | None = None
    instrument_id: int
    venue_code: str | None = None
    expected_last_session: date
    data_last_session: date
    refreshed: bool
    is_stale: bool
    refresh_warning: str | None = None
    price_source: str
    price_basis: str
