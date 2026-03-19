"""Portfolio simulation — NAV-based equity curve with long + short P&L.

Takes a Portfolio configuration and prices, runs the simulation:
1. Compute strategy weights
2. Optionally compute regime and pass to strategy
3. Enforce max_leverage constraint
4. Simulate daily NAV changes based on weights and price returns

P&L computation:
  Long P&L  =  weight * (price_t / price_{t-1} - 1)
  Short P&L = -weight * (price_t / price_{t-1} - 1)
  (where weight for shorts is negative, so -weight is positive)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from trading_engine.types import (
    Portfolio,
    PortfolioResult,
    PriceFrame,
    RegimeSeries,
)
from trading_engine.factor_analysis.cross_sectional import analyze_cross_section
from trading_engine.factor_analysis.regime import detect_regime


def run_portfolio(
    portfolio: Portfolio,
    prices: dict[str, PriceFrame],
) -> PortfolioResult:
    """Run a portfolio simulation.

    Args:
        portfolio: Configuration (strategy, capital, leverage, regime).
        prices: Dict mapping symbol -> PriceFrame.

    Returns:
        PortfolioResult with equity curve, trades, and applied weights.
    """
    symbols = list(prices.keys())

    # Step 1: Compute regime if configured
    regime: RegimeSeries | None = None
    if portfolio.regime_config is not None:
        rc = portfolio.regime_config
        cross = analyze_cross_section(
            factor=rc.factor,
            universe=rc.universe,
            prices=prices,
            threshold=rc.threshold,
        )
        regime = detect_regime(cross.breadth, rc.thresholds)

    # Step 2: Get strategy weights
    output = portfolio.strategy.compute(symbols, prices, regime)
    weights = output.weights

    if weights.empty:
        return PortfolioResult(
            equity_curve=pd.Series(dtype=float),
            trades=output.trades,
            weights=weights,
        )

    # Step 3: Enforce max_leverage
    weights = _enforce_leverage(weights, portfolio.max_leverage)

    # Step 4: Build close price matrix aligned with weights
    close_matrix = _build_close_matrix(symbols, prices, weights.index)

    # Step 5: Simulate NAV
    equity_curve = _simulate_nav(
        weights, close_matrix, portfolio.initial_capital
    )

    # Recompute trades from the potentially leverage-adjusted weights
    from trading_engine.strategy.utils import weight_transitions_to_trades
    trades = weight_transitions_to_trades(weights, prices)

    return PortfolioResult(
        equity_curve=equity_curve,
        trades=trades,
        weights=weights,
    )


def _enforce_leverage(weights: pd.DataFrame, max_leverage: float) -> pd.DataFrame:
    """Scale weights so sum(abs(weights_t)) <= max_leverage at each time step.

    If the total absolute weight exceeds max_leverage, all weights are
    scaled proportionally to fit within the constraint.
    """
    abs_sum = weights.abs().sum(axis=1)
    scale = (max_leverage / abs_sum).clip(upper=1.0)

    # Only scale rows that exceed the limit
    needs_scaling = abs_sum > max_leverage
    if needs_scaling.any():
        weights = weights.copy()
        weights.loc[needs_scaling] = weights.loc[needs_scaling].multiply(
            scale[needs_scaling], axis=0
        )

    return weights


def _build_close_matrix(
    symbols: list[str],
    prices: dict[str, PriceFrame],
    index: pd.DatetimeIndex,
) -> pd.DataFrame:
    """Build a DataFrame of close prices aligned with the weight index."""
    close_data = {}
    for symbol in symbols:
        if symbol in prices:
            close = prices[symbol].data["close"].reindex(index)
            close_data[symbol] = close

    return pd.DataFrame(close_data)


def _simulate_nav(
    weights: pd.DataFrame,
    close_matrix: pd.DataFrame,
    initial_capital: float,
) -> pd.Series:
    """Simulate NAV using daily returns weighted by position sizes.

    NAV_t = NAV_{t-1} * (1 + sum(weight_i * return_i) for all symbols i)

    For long positions: weight > 0, positive return = gain
    For short positions: weight < 0, positive return = loss
    This works naturally because:
      short P&L = weight * return = negative_weight * positive_return = loss
    """
    # Daily returns for each symbol
    returns = close_matrix.pct_change()

    # Portfolio daily return = sum of (weight * asset return) across symbols
    # Use previous day's weight for today's return
    shifted_weights = weights.shift(1)
    portfolio_returns = (shifted_weights * returns).sum(axis=1)

    # Build equity curve
    nav = pd.Series(index=weights.index, dtype=float)
    nav.iloc[0] = initial_capital

    for i in range(1, len(nav)):
        nav.iloc[i] = nav.iloc[i - 1] * (1 + portfolio_returns.iloc[i])

    return nav
