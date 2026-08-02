"""Relative-strength trend against a market benchmark."""
from __future__ import annotations

import pandas as pd


def normalized_relative_strength(
    close: pd.Series,
    benchmark_close: pd.Series,
) -> pd.Series:
    """Return close / benchmark, rebased to the latest stock close.

    The latest common observation is used only as a display-scale anchor. The
    resulting values can share the stock's price pane while preserving the
    direction and percentage movement of the relative-strength ratio.
    """
    stock = pd.to_numeric(close, errors="coerce").sort_index()
    benchmark = pd.to_numeric(benchmark_close, errors="coerce").sort_index()
    aligned_benchmark = benchmark.reindex(stock.index).ffill()
    valid = stock.notna() & aligned_benchmark.notna() & (aligned_benchmark > 0)

    result = pd.Series(index=stock.index, dtype=float, name="relative_strength")
    if not valid.any():
        return result

    ratio = stock.loc[valid] / aligned_benchmark.loc[valid]
    anchor_ratio = ratio.iloc[-1]
    if pd.isna(anchor_ratio) or anchor_ratio == 0:
        return result
    result.loc[ratio.index] = ratio / anchor_ratio * stock.loc[valid].iloc[-1]
    return result
