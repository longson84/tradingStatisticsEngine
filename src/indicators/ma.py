"""Moving average computation utilities."""
from __future__ import annotations

from typing import Literal

import numpy as np
import pandas as pd


def moving_average(series: pd.Series, ma_type: Literal["SMA", "EMA", "WMA"], length: int) -> pd.Series:
    """Compute a moving average of the given type over *series*.

    Args:
        series: Price (or any numeric) series.
        ma_type: One of ``"SMA"``, ``"EMA"``, or ``"WMA"``.
        length: Look-back window / span.

    Returns:
        A ``pd.Series`` of the same index with the MA values.
    """
    if ma_type == "SMA":
        return series.rolling(length).mean()
    elif ma_type == "EMA":
        return series.ewm(span=length, adjust=False).mean()
    elif ma_type == "WMA":
        weights = np.arange(1, length + 1, dtype=float)
        weights /= weights.sum()

        def _wma(x):
            return np.dot(x, weights)

        return series.rolling(length).apply(_wma, raw=True)
    else:
        raise ValueError(f"Unknown MA type: {ma_type}")
