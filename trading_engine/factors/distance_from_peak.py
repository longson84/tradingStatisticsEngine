"""Distance from Peak factor — measures drawdown from rolling high."""
from __future__ import annotations

from trading_engine.types import FactorComputeError, FactorSeries, PriceFrame


class DistanceFromPeak:
    """Factor: how far price is below its rolling window peak.

    Output is in (-1, 0] where:
    - 0.0 = at the peak (no drawdown)
    - -0.20 = 20% below the peak

    Implements the Factor protocol.
    """

    def __init__(self, window: int = 252):
        self.window = window

    def compute(self, prices: PriceFrame) -> FactorSeries:
        close = prices.data["close"]
        if len(close) < self.window:
            raise FactorComputeError(
                f"Need at least {self.window} bars for DistanceFromPeak, "
                f"got {len(close)}"
            )

        rolling_max = close.rolling(window=self.window).max()

        if (rolling_max == 0).any():
            raise FactorComputeError(
                f"Rolling max contains zero for {prices.symbol}"
            )

        values = (close / rolling_max - 1).dropna()
        return FactorSeries(
            name=f"DistFromPeak({self.window})",
            values=values,
            metadata={"window": self.window},
        )
