"""Regime detection — labels time periods based on breadth thresholds.

Pure function: breadth series + thresholds -> RegimeSeries.
Wired via run_portfolio(regime_config=...), NOT inside the strategy.
"""
from __future__ import annotations

import pandas as pd

from trading_engine.types import InsufficientDataError, RegimeSeries


def detect_regime(
    breadth: pd.Series,
    thresholds: tuple[float, float],
) -> RegimeSeries:
    """Label each time period as risk_on, risk_off, or transition.

    Args:
        breadth: A [0, 1] series representing market breadth
            (e.g., % of universe above a moving average).
        thresholds: (lower, upper) cutoffs.
            - breadth < lower -> "risk_off"
            - breadth > upper -> "risk_on"
            - otherwise -> "transition"

    Returns:
        RegimeSeries with labels and the underlying breadth.

    Raises:
        ValueError: If thresholds are invalid.
        InsufficientDataError: If breadth series is empty.
    """
    lower, upper = thresholds

    if lower >= upper:
        raise ValueError(
            f"Lower threshold ({lower}) must be less than upper ({upper})"
        )
    if lower < 0 or upper > 1:
        raise ValueError(
            f"Thresholds must be in [0, 1], got ({lower}, {upper})"
        )

    breadth = breadth.dropna()
    if breadth.empty:
        raise InsufficientDataError("Breadth series is empty")

    labels = pd.Series(index=breadth.index, dtype=str)
    labels[breadth < lower] = "risk_off"
    labels[breadth > upper] = "risk_on"
    labels[(breadth >= lower) & (breadth <= upper)] = "transition"

    return RegimeSeries(labels=labels, breadth=breadth)
