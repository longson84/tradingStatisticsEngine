"""Look-ahead bias detection — verifies strategies don't use future data.

assert_no_leakage() works by running a strategy twice:
1. Full dataset
2. Truncated dataset (last N bars removed)

If the weights for overlapping dates differ, the strategy is using
future data (look-ahead bias).
"""
from __future__ import annotations

import pandas as pd

from trading_engine.types import PriceFrame, Strategy, StrategyOutputError


def assert_no_leakage(
    strategy: Strategy,
    symbols: list[str],
    prices: dict[str, PriceFrame],
    truncate_bars: int = 20,
    tolerance: float = 1e-10,
) -> None:
    """Verify a strategy does not use future price data.

    Runs the strategy on full data and on truncated data. If weights
    for overlapping dates differ, the strategy has look-ahead bias.

    Args:
        strategy: The strategy to test.
        symbols: Symbols to test with.
        prices: Full price data.
        truncate_bars: Number of bars to remove from the end.
        tolerance: Max allowed weight difference (for floating point).

    Raises:
        StrategyOutputError: If look-ahead bias is detected.
    """
    # Run on full data
    full_output = strategy.compute(symbols, prices, regime=None)
    full_weights = full_output.weights

    # Run on truncated data
    truncated_prices: dict[str, PriceFrame] = {}
    for symbol, pf in prices.items():
        if symbol in symbols:
            truncated_data = pf.data.iloc[:-truncate_bars]
            if truncated_data.empty:
                continue
            truncated_prices[symbol] = PriceFrame(
                symbol=pf.symbol,
                data=truncated_data,
                source=pf.source,
            )

    if not truncated_prices:
        return  # not enough data to test

    trunc_output = strategy.compute(
        [s for s in symbols if s in truncated_prices],
        truncated_prices,
        regime=None,
    )
    trunc_weights = trunc_output.weights

    # Compare overlapping dates
    overlap_dates = full_weights.index.intersection(trunc_weights.index)
    overlap_symbols = [
        s for s in full_weights.columns if s in trunc_weights.columns
    ]

    if overlap_dates.empty or not overlap_symbols:
        return

    full_overlap = full_weights.loc[overlap_dates, overlap_symbols]
    trunc_overlap = trunc_weights.loc[overlap_dates, overlap_symbols]

    diff = (full_overlap - trunc_overlap).abs()
    max_diff = diff.max().max()

    if max_diff > tolerance:
        # Find the first offending date and symbol
        offending = diff.stack()
        offending = offending[offending > tolerance]
        first = offending.index[0]

        raise StrategyOutputError(
            f"Look-ahead bias detected! Strategy produced different weights "
            f"for date={first[0]}, symbol={first[1]} when future data was "
            f"removed. Max weight difference: {max_diff:.6f}. "
            f"The strategy is using future price data."
        )
