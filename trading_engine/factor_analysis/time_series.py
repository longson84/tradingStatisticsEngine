"""Time-series factor analysis — 1 symbol, 1 factor, over time."""
from __future__ import annotations

import numpy as np
from scipy import stats as scipy_stats

from trading_engine.types import FactorAnalysisResult, FactorSeries, InsufficientDataError


def percentile_breakdown(
    factor: FactorSeries,
    buckets: list[int] | None = None,
) -> FactorAnalysisResult:
    """Compute percentile breakdown of a factor's historical values.

    Args:
        factor: The factor series to analyze.
        buckets: Percentile levels to compute (default: [5, 10, 25, 50, 75, 90, 95]).

    Returns:
        FactorAnalysisResult with percentile thresholds and current position.
    """
    if buckets is None:
        buckets = [5, 10, 25, 50, 75, 90, 95]

    values = factor.values.dropna()
    if len(values) < 2:
        raise InsufficientDataError(
            f"Need at least 2 data points for percentile breakdown, "
            f"got {len(values)}"
        )

    percentiles = {p: float(np.percentile(values, p)) for p in buckets}
    current_value = float(values.iloc[-1])
    current_percentile = float(scipy_stats.percentileofscore(values, current_value))

    return FactorAnalysisResult(
        factor_name=factor.name,
        percentiles=percentiles,
        current_percentile=current_percentile,
        current_value=current_value,
        history_length_days=len(values),
    )


def rarity_analysis(factor: FactorSeries) -> FactorAnalysisResult:
    """Analyze rarity of the current factor value in historical context.

    Uses fine-grained percentile buckets focused on the tails
    (1st, 5th, 10th, 15th, 20th percentiles).
    """
    return percentile_breakdown(
        factor, buckets=[1, 5, 10, 15, 20, 25, 30, 40, 50]
    )
