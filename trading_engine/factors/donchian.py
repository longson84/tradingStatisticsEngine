"""Donchian Channel factor."""
from __future__ import annotations

import pandas as pd

from trading_engine.types import FactorComputeError, FactorSeries, PriceFrame


class DonchianChannel:
    """Factor: Donchian Channel position — where price sits relative to the channel.

    Output value = (close - lower) / (upper - lower), so:
    - 0.0 = at lower channel
    - 1.0 = at upper channel

    Implements the Factor protocol.
    """

    def __init__(self, entry_length: int = 20, exit_length: int = 10):
        self.entry_length = entry_length
        self.exit_length = exit_length

    def compute(self, prices: PriceFrame) -> FactorSeries:
        high = prices.data["high"]
        low = prices.data["low"]
        close = prices.data["close"]

        min_length = max(self.entry_length, self.exit_length)
        if len(close) < min_length:
            raise FactorComputeError(
                f"Need at least {min_length} bars for Donchian, got {len(close)}"
            )

        upper = high.rolling(self.entry_length).max().shift(1)
        lower = low.rolling(self.exit_length).min().shift(1)

        channel_width = upper - lower
        # Replace zero width with NaN to avoid division by zero
        channel_width = channel_width.replace(0, float("nan"))

        values = ((close - lower) / channel_width).dropna()
        return FactorSeries(
            name=f"Donchian({self.entry_length}/{self.exit_length})",
            values=values,
            metadata={
                "entry_length": self.entry_length,
                "exit_length": self.exit_length,
            },
        )

    def compute_channels(self, prices: PriceFrame) -> tuple[pd.Series, pd.Series]:
        """Return raw (upper, lower) channels for charting."""
        high = prices.data["high"]
        low = prices.data["low"]
        upper = high.rolling(self.entry_length).max().shift(1)
        lower = low.rolling(self.exit_length).min().shift(1)
        return upper, lower
