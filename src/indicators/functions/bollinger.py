"""Bollinger Bands computation."""
from __future__ import annotations

from typing import Tuple

import pandas as pd

from src.indicators.functions.ma import moving_average


def bollinger_bands(
    close: pd.Series,
    period: int,
    num_std: float,
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Compute Bollinger Bands.

    Args:
        close: Close price series.
        period: SMA look-back period.
        num_std: Number of standard deviations for band width.

    Returns:
        (sma, upper_band, lower_band)
    """
    sma = moving_average(close, "SMA", period)
    std = close.rolling(period).std()
    upper = sma + std * num_std
    lower = sma - std * num_std
    return sma, upper, lower
