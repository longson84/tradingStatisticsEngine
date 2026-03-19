"""AHR999 index computation."""
from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd


def ahr999(close: pd.Series) -> pd.Series:
    """Compute the AHR999 Bitcoin accumulation index.

    Combines price-to-model ratio with price-to-200MA ratio.
    Result < 0.45 is historically a strong accumulation zone.

    Args:
        close: BTC-USD close price series with a DatetimeIndex.

    Returns:
        AHR999 value series (NaNs dropped from 200-bar MA warmup).
    """
    genesis_date = datetime(2009, 1, 3)
    days_passed = np.maximum((close.index - genesis_date).days, 1)

    p_est = 10 ** (5.84 * np.log10(days_passed) - 17.01)
    ma200 = close.rolling(window=200).mean()

    return ((close / p_est) * (close / ma200)).dropna()
