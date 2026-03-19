"""Moving average factors — MA computation and price-to-MA ratio."""
from __future__ import annotations

from typing import Literal

import numpy as np
import pandas as pd

from trading_engine.types import FactorComputeError, FactorSeries, PriceFrame


MaType = Literal["SMA", "EMA", "WMA"]


def compute_ma(series: pd.Series, ma_type: MaType, length: int) -> pd.Series:
    """Compute a moving average of the given type.

    This is the core utility used by MovingAverage and MovingAverageRatio
    factors, and also available for direct use by strategies.
    """
    if length < 1:
        raise FactorComputeError(f"MA length must be >= 1, got {length}")

    if ma_type == "SMA":
        return series.rolling(length).mean()
    elif ma_type == "EMA":
        return series.ewm(span=length, adjust=False).mean()
    elif ma_type == "WMA":
        weights = np.arange(1, length + 1, dtype=float)
        weights /= weights.sum()
        return series.rolling(length).apply(lambda x: np.dot(x, weights), raw=True)
    else:
        raise FactorComputeError(f"Unknown MA type: {ma_type}")


class MovingAverage:
    """Factor: compute a moving average of close prices.

    Implements the Factor protocol.
    """

    def __init__(self, ma_type: MaType = "SMA", length: int = 50):
        self.ma_type = ma_type
        self.length = length

    def compute(self, prices: PriceFrame) -> FactorSeries:
        close = prices.data["close"]
        if len(close) < self.length:
            raise FactorComputeError(
                f"Need at least {self.length} bars for {self.ma_type}({self.length}), "
                f"got {len(close)}"
            )
        values = compute_ma(close, self.ma_type, self.length).dropna()
        return FactorSeries(
            name=f"{self.ma_type}({self.length})",
            values=values,
            metadata={"ma_type": self.ma_type, "length": self.length},
        )


class MovingAverageRatio:
    """Factor: price / MA - 1. Measures how far price is from its MA.

    Positive = price above MA, negative = price below MA.
    Implements the Factor protocol.
    """

    def __init__(self, ma_type: MaType = "SMA", length: int = 50):
        self.ma_type = ma_type
        self.length = length

    def compute(self, prices: PriceFrame) -> FactorSeries:
        close = prices.data["close"]
        if len(close) < self.length:
            raise FactorComputeError(
                f"Need at least {self.length} bars for MA ratio, got {len(close)}"
            )

        ma = compute_ma(close, self.ma_type, self.length)

        # Guard against zero MA (e.g., if all prices are 0)
        if (ma == 0).any():
            raise FactorComputeError(
                f"MA contains zero values for {prices.symbol} — "
                f"cannot compute ratio"
            )

        values = (close / ma - 1).dropna()
        return FactorSeries(
            name=f"{self.ma_type}({self.length}) Ratio",
            values=values,
            metadata={"ma_type": self.ma_type, "length": self.length},
        )
