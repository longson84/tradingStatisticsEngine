"""Buy and Hold strategy — constant weight allocation."""
from __future__ import annotations

import pandas as pd

from trading_engine.types import PriceFrame, RegimeSeries
from trading_engine.strategy.base import BaseStrategy


class BuyAndHold(BaseStrategy):
    """Constant weight allocation across all symbols.

    Default weight = 1.0 (fully invested in each symbol).
    Useful as a benchmark strategy.
    """

    def __init__(self, weight: float = 1.0):
        self.weight = weight

    def _compute_weights(
        self,
        symbols: list[str],
        prices: dict[str, PriceFrame],
        regime: RegimeSeries | None = None,
    ) -> pd.DataFrame:
        all_weights = {}

        for symbol in symbols:
            if symbol not in prices:
                continue
            idx = prices[symbol].data.index
            all_weights[symbol] = pd.Series(self.weight, index=idx)

        if not all_weights:
            return pd.DataFrame()

        return pd.DataFrame(all_weights).fillna(0.0)
