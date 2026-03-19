"""AHR999 factor — Bitcoin accumulation index.

Combines price-to-model ratio with price-to-200MA ratio.
Values < 0.45 historically indicate strong accumulation zones.
Only applicable to BTC-USD.
"""
from __future__ import annotations

from datetime import datetime

import numpy as np

from trading_engine.types import FactorComputeError, FactorSeries, PriceFrame


class AHR999:
    """Factor: AHR999 Bitcoin accumulation index.

    Implements the Factor protocol.
    Only meaningful for BTC-USD — will compute on any symbol but results
    only make sense for Bitcoin.
    """

    GENESIS_DATE = datetime(2009, 1, 3)
    MA_WINDOW = 200

    def compute(self, prices: PriceFrame) -> FactorSeries:
        close = prices.data["close"]
        if len(close) < self.MA_WINDOW:
            raise FactorComputeError(
                f"Need at least {self.MA_WINDOW} bars for AHR999, "
                f"got {len(close)}"
            )

        days_passed = np.maximum(
            (close.index - self.GENESIS_DATE).days, 1
        )
        p_est = 10 ** (5.84 * np.log10(days_passed) - 17.01)
        ma200 = close.rolling(window=self.MA_WINDOW).mean()

        # Guard against zero MA
        if (ma200.dropna() == 0).any():
            raise FactorComputeError(
                f"200-day MA contains zero for {prices.symbol}"
            )

        values = ((close / p_est) * (close / ma200)).dropna()
        return FactorSeries(
            name="AHR999",
            values=values,
            metadata={"ma_window": self.MA_WINDOW},
        )
