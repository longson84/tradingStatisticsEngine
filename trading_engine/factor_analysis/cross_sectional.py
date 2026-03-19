"""Cross-sectional factor analysis — N symbols, 1 factor, per time step.

Answers: "how does this factor distribute across a universe right now?"
Produces market breadth indicators, universe rankings, and threshold statistics.
"""
from __future__ import annotations

import pandas as pd

from trading_engine.types import (
    CrossSectionalResult,
    Factor,
    InsufficientDataError,
    PriceFrame,
)


def analyze_cross_section(
    factor: Factor,
    universe: list[str],
    prices: dict[str, PriceFrame],
    threshold: float | None = None,
) -> CrossSectionalResult:
    """Compute cross-sectional analysis across a universe of symbols.

    For each time step, computes the factor for every symbol in the universe,
    then aggregates: counts above threshold, percentage, breadth, ranks, median.

    Args:
        factor: The Factor to compute for each symbol.
        universe: List of symbol names.
        prices: Dict mapping symbol -> PriceFrame.
        threshold: Value above which to count (for breadth). If None, uses 0.

    Returns:
        CrossSectionalResult with time-indexed aggregation series.

    Raises:
        ValueError: If universe is empty.
        InsufficientDataError: If no overlapping dates across universe.
    """
    if not universe:
        raise ValueError("Universe cannot be empty")

    if threshold is None:
        threshold = 0.0

    # Compute factor for each symbol, align to a common date index
    factor_values: dict[str, pd.Series] = {}
    for symbol in universe:
        if symbol not in prices:
            continue  # skip symbols without price data
        series = factor.compute(prices[symbol])
        factor_values[symbol] = series.values

    if not factor_values:
        raise InsufficientDataError(
            f"No factor values computed for any symbol in universe"
        )

    # Combine into a DataFrame: rows = dates, columns = symbols
    factor_df = pd.DataFrame(factor_values)

    # Drop rows where ALL symbols are NaN
    factor_df = factor_df.dropna(how="all")

    if factor_df.empty:
        raise InsufficientDataError("No overlapping dates across universe")

    n_symbols = factor_df.count(axis=1)  # non-NaN count per row

    # Counts above threshold at each time step
    above = factor_df.gt(threshold)
    counts_above = above.sum(axis=1)
    pct_above = (counts_above / n_symbols * 100).fillna(0)
    breadth = (counts_above / n_symbols).fillna(0)

    # Rank per symbol per time step (ascending: 1 = lowest factor value)
    ranks = factor_df.rank(axis=1, method="average", ascending=True)

    # Universe median at each time step
    universe_median = factor_df.median(axis=1)

    return CrossSectionalResult(
        factor_name=factor.compute(prices[universe[0]]).name if universe else "",
        universe=universe,
        counts_above=counts_above,
        pct_above=pct_above,
        breadth=breadth,
        ranks=ranks,
        universe_median=universe_median,
    )
