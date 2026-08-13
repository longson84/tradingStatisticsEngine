"""Canonical cross-sectional Universe statistics."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from trading_engine.types import InsufficientDataError, UniverseStatsSeries


def calculate_universe_stats(
    closes: pd.DataFrame,
    *,
    member_count: int,
    window: int = 200,
    minimum_coverage: float = 0.5,
) -> UniverseStatsSeries:
    """Calculate median distance from trailing closing high and low.

    ``closes`` is a date-by-instrument panel keyed by canonical instrument ID.
    Missing values are carried forward only after an instrument's first observed
    close. Leading pre-listing values remain missing.
    """
    if member_count < 1:
        raise ValueError("member_count must be positive")
    if window < 2:
        raise ValueError("window must be at least 2")
    if not 0 < minimum_coverage <= 1:
        raise ValueError("minimum_coverage must be in (0, 1]")
    if closes.empty:
        raise InsufficientDataError("No stored closing prices are available")

    panel = closes.sort_index().astype(float).replace([np.inf, -np.inf], np.nan)
    panel = panel.ffill()
    trailing_high = panel.rolling(window=window, min_periods=window).max()
    trailing_low = panel.rolling(window=window, min_periods=window).min()
    distance_high = panel.divide(trailing_high).subtract(1.0).multiply(100.0)
    distance_low = panel.divide(trailing_low).subtract(1.0).multiply(100.0)

    eligible = distance_high.notna() & distance_low.notna()
    eligible_count = eligible.sum(axis=1).astype(int)
    required_count = max(1, math.ceil(member_count * minimum_coverage))
    included = eligible_count >= required_count
    if not included.any():
        raise InsufficientDataError(
            f"No date has {required_count} members with {window} observations"
        )

    high_median = distance_high.where(eligible).median(axis=1)[included]
    low_median = distance_low.where(eligible).median(axis=1)[included]
    counts = eligible_count[included]
    coverage = counts.divide(member_count).multiply(100.0)
    return UniverseStatsSeries(
        median_distance_from_high=high_median,
        median_distance_from_low=low_median,
        eligible_count=counts,
        coverage_pct=coverage,
    )
