"""Distance from Peak factor — measures drawdown from rolling high."""
from __future__ import annotations

from typing import Any

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

    def context(self, prices: PriceFrame) -> dict[str, Any]:
        """Return factor-specific live context for display.

        For DistanceFromPeak this is: the date and price of the current
        rolling-window peak, how many sessions ago it was set, and how many
        sessions remain before it potentially rolls off the window.
        """
        close = prices.data["close"]
        window_data = close.iloc[-self.window:]
        peak_price = float(window_data.max())
        peak_date = window_data.idxmax()
        sessions_from_peak = len(close.loc[peak_date:]) - 1
        remaining_sessions = max(0, self.window - sessions_from_peak)
        return {
            "peak_price": peak_price,
            "peak_date": str(peak_date.date()),
            "sessions_from_peak": sessions_from_peak,
            "remaining_sessions": remaining_sessions,
        }
