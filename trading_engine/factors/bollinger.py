"""Bollinger Bands factor."""
from __future__ import annotations

import pandas as pd

from trading_engine.types import FactorComputeError, FactorSeries, PriceFrame
from trading_engine.factors.moving_average import compute_ma


class BollingerBands:
    """Factor: Bollinger Band position — where price sits relative to the bands.

    Output value = (close - lower) / (upper - lower), so:
    - 0.0 = at lower band
    - 0.5 = at middle (SMA)
    - 1.0 = at upper band
    - > 1.0 = above upper band
    - < 0.0 = below lower band

    Implements the Factor protocol.
    """

    def __init__(self, period: int = 20, num_std: float = 2.0):
        self.period = period
        self.num_std = num_std

    def compute(self, prices: PriceFrame) -> FactorSeries:
        close = prices.data["close"]
        if len(close) < self.period:
            raise FactorComputeError(
                f"Need at least {self.period} bars for Bollinger, got {len(close)}"
            )

        sma = compute_ma(close, "SMA", self.period)
        std = close.rolling(self.period).std()
        upper = sma + std * self.num_std
        lower = sma - std * self.num_std

        band_width = upper - lower
        if (band_width == 0).any():
            raise FactorComputeError(
                f"Bollinger band width is zero for {prices.symbol} — "
                f"constant price in window"
            )

        values = ((close - lower) / band_width).dropna()
        return FactorSeries(
            name=f"BB({self.period}, {self.num_std}σ)",
            values=values,
            metadata={
                "period": self.period,
                "num_std": self.num_std,
            },
        )

    def compute_bands(self, prices: PriceFrame) -> tuple[pd.Series, pd.Series, pd.Series]:
        """Return raw (sma, upper, lower) bands for charting."""
        close = prices.data["close"]
        sma = compute_ma(close, "SMA", self.period)
        std = close.rolling(self.period).std()
        upper = sma + std * self.num_std
        lower = sma - std * self.num_std
        return sma, upper, lower
