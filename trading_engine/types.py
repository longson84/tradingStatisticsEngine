"""Centralized types for the trading_engine library.

All shared dataclasses, Protocols, and custom exceptions live here.
Every layer imports from this single file — no scattered type definitions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal, Protocol, runtime_checkable

import pandas as pd


# =============================================================================
# Custom Exceptions
# =============================================================================

class DataLoadError(Exception):
    """Raised when a data source fails to load after retries."""


class FactorComputeError(Exception):
    """Raised when a factor computation fails (e.g., division by zero price)."""


class InsufficientDataError(Exception):
    """Raised when there isn't enough data for a computation."""


class StrategyOutputError(Exception):
    """Raised when strategy output is invalid (e.g., NaN in weights)."""


class ConfigError(Exception):
    """Raised for invalid BacktestConfig or comparison configuration."""


# =============================================================================
# Layer 1: Data
# =============================================================================

@dataclass
class PriceFrame:
    """Unified OHLCV container for a single symbol.

    data columns: open, high, low, close, volume
    Index: DatetimeIndex (daily bars).
    """
    symbol: str
    data: pd.DataFrame
    source: str  # "yfinance" | "vnstock" | "csv"

    def __post_init__(self) -> None:
        required = {"open", "high", "low", "close"}
        actual = set(self.data.columns.str.lower())
        missing = required - actual
        if missing:
            raise ValueError(
                f"PriceFrame for {self.symbol} missing columns: {missing}"
            )


@runtime_checkable
class DataLoader(Protocol):
    """Protocol for all data sources."""
    def load(self, symbol: str, start: date, end: date) -> PriceFrame: ...


# =============================================================================
# Layer 2: Factor
# =============================================================================

@dataclass
class FactorSeries:
    """Result of computing a factor over a PriceFrame."""
    name: str
    values: pd.Series
    metadata: dict = field(default_factory=dict)


@runtime_checkable
class Factor(Protocol):
    """Protocol for all factors (indicators + analytical factors)."""
    def compute(self, prices: PriceFrame) -> FactorSeries: ...


# =============================================================================
# Layer 3: Factor Analysis
# =============================================================================

@dataclass
class FactorAnalysisResult:
    """Result of time-series factor analysis (1 symbol, 1 factor, over time)."""
    factor_name: str
    percentiles: dict[int, float]  # percentile → threshold value
    current_percentile: float
    current_value: float
    history_length_days: int


@dataclass
class CrossSectionalResult:
    """Result of cross-sectional analysis (N symbols, 1 factor, per time step)."""
    factor_name: str
    universe: list[str]
    counts_above: pd.Series       # count(factor > threshold) at each t
    pct_above: pd.Series          # % of universe above threshold at each t
    breadth: pd.Series            # normalized [0, 1]
    ranks: pd.DataFrame           # shape (time x symbols), rank per symbol per t
    universe_median: pd.Series    # median factor value across universe at each t


@dataclass
class RegimeSeries:
    """Time-indexed regime labels derived from breadth analysis."""
    labels: pd.Series  # values: "risk_on" | "risk_off" | "transition"
    breadth: pd.Series  # the underlying breadth series used


@dataclass(frozen=True)
class RegimeConfig:
    """Configuration for regime-filtered portfolio simulation.

    Wired via run_portfolio(regime_config=...) — not inside the strategy.
    Portfolio computes RegimeSeries and passes it to Strategy.compute().
    """
    factor: Factor
    universe: list[str]
    threshold: float
    thresholds: tuple[float, float]  # (lower, upper) for risk_off/transition/risk_on


# =============================================================================
# Layer 4: Strategy
# =============================================================================

@dataclass
class WeightEvent:
    """Records a weight change within a single trade (scaling in/out)."""
    date: date
    weight: float
    price: float


@dataclass
class ExplainRecord:
    """Optional context explaining why a trade was opened."""
    active_factors: dict[str, float]   # factor_name -> value at entry
    breadth_at_entry: float
    regime_at_entry: str               # "risk_on" | "risk_off" | "transition"


@dataclass
class Trade:
    """A single trade (long or short), from entry to exit.

    Zero-crossing rule: weight 0.5 -> -0.3 produces 2 Trade records
    (exit long + enter short) atomically in the same bar.

    Partial weight changes (0.5 -> 0.3, same direction) append to
    weight_history without creating a new Trade record.
    """
    symbol: str
    direction: Literal["long", "short"]  # explicit, do not derive from sign(weight)
    entry_date: date
    entry_price: float
    entry_weight: float
    exit_date: date | None = None
    exit_price: float | None = None
    weight_history: list[WeightEvent] = field(default_factory=list)
    return_pct: float | None = None      # portfolio-weighted realized P&L
    holding_days: int | None = None
    mae_pct: float | None = None         # max adverse excursion
    mfe_pct: float | None = None         # max favorable excursion
    explain: ExplainRecord | None = None


@dataclass
class StrategyOutput:
    """What a Strategy.compute() returns."""
    weights: pd.DataFrame     # shape: (time x symbols), values in [-1, 1]
    trades: list[Trade]       # derived from weight transitions


@runtime_checkable
class Strategy(Protocol):
    """Protocol for all strategies."""
    def compute(
        self,
        symbols: list[str],
        prices: dict[str, PriceFrame],
        regime: RegimeSeries | None = None,
    ) -> StrategyOutput: ...


# =============================================================================
# Layer 5: Portfolio
# =============================================================================

@dataclass
class Portfolio:
    """Configuration for a portfolio simulation run.

    Strategy expresses conviction via weights.
    Portfolio enforces capital constraints (max_leverage) and regime filter.
    """
    initial_capital: float
    strategy: Strategy
    max_leverage: float = 1.0
    regime_config: RegimeConfig | None = None


@dataclass
class PortfolioResult:
    """Output of run_portfolio()."""
    equity_curve: pd.Series    # NAV over time
    trades: list[Trade]
    weights: pd.DataFrame      # the weight matrix that was applied


# =============================================================================
# Layer 6: Performance
# =============================================================================

@dataclass
class TradeDistribution:
    """Distribution statistics for trade analysis."""
    return_buckets: dict[str, int]    # bucket_label -> count
    mae_buckets: dict[str, int]
    mfe_buckets: dict[str, int]


@dataclass
class PerformanceReport:
    """Output of analyze_performance()."""
    total_return_pct: float
    cagr: float
    sharpe_ratio: float
    max_drawdown_pct: float
    win_rate: float
    avg_return_per_trade: float
    avg_holding_days: float
    monthly_returns: pd.DataFrame     # (year x month) for heatmap
    annual_returns: pd.Series
    trade_distribution: TradeDistribution


# =============================================================================
# Comparison Framework
# =============================================================================

@dataclass
class BacktestConfig:
    """A single backtest configuration for run_comparison().

    No DataLoader — caller pre-fetches prices and passes them separately.
    Reason: a 50-config parameter sweep needs 1 network call, not 50.
    """
    strategy: Strategy
    symbols: list[str]
    start: date
    end: date


@dataclass
class ComparisonReport:
    """Output of run_comparison(). Supports partial failure."""
    results: list[PortfolioResult]
    configs: list[BacktestConfig]
    errors: list[tuple[BacktestConfig, Exception]]
