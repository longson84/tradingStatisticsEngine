"""Peak and drawdown indicator computations."""
from __future__ import annotations

import pandas as pd


def distance_from_peak(prices: pd.Series, window: int) -> pd.Series:
    """Compute how far each value is below its rolling *window*-period high.

    The result is expressed as a fraction in ``(-1, 0]``, where ``0`` means
    the current value equals the peak and ``-0.20`` means it is 20 % below.

    Args:
        prices: Price (or any numeric) series.
        window: Look-back window in bars.

    Returns:
        ``(prices / rolling_max) - 1``, with leading NaNs dropped.
    """
    rolling_max = prices.rolling(window=window).max()
    return (prices / rolling_max) - 1
