"""Factor Threshold Strategy — binary long/flat signal from any factor.

The strategy is deliberately factor-agnostic: it only cares whether the
factor value is above or below a threshold.  Swap the factor to get a
completely different strategy with no other code changes.

Confirmation lag semantics
--------------------------
Entry: factor must be continuously > threshold for (buy_lag + 1) bars.
       Any dip back below the threshold resets the confirmation counter.
Exit:  factor must be continuously ≤ threshold for (sell_lag + 1) bars.
       Any recovery above the threshold resets the exit counter.

Examples
--------
Price vs SMA(50), enter same day, exit after 2-day confirmation:
    factor    = MovingAverageRatio(ma_type="SMA", length=50)
    strategy  = FactorThresholdStrategy(factor, threshold=0.0, buy_lag=0, sell_lag=2)

Price vs EMA(20), both with 1-day confirmation:
    factor    = MovingAverageRatio(ma_type="EMA", length=20)
    strategy  = FactorThresholdStrategy(factor, threshold=0.0, buy_lag=1, sell_lag=1)
"""
from __future__ import annotations

import pandas as pd

from trading_engine.types import Factor, PriceFrame, RegimeSeries
from trading_engine.strategy.base import BaseStrategy


class FactorThresholdStrategy(BaseStrategy):
    """Long (weight=1) when factor > threshold; flat (weight=0) otherwise.

    Works on any symbol list: the factor is computed independently per symbol
    and each symbol gets its own confirmation-lag state machine.

    Parameters
    ----------
    factor : Factor
        Any object implementing the Factor protocol
        (compute(PriceFrame) -> FactorSeries).
    threshold : float
        Crossing level.  Long signal fires when factor_value > threshold.
        Default 0.0 works for MovingAverageRatio (price/MA - 1 > 0).
    buy_lag : int
        Additional confirmation bars needed before entering.
        0 = enter on the crossover bar itself.
    sell_lag : int
        Additional confirmation bars needed before exiting.
        0 = exit on the first bar the factor drops below threshold.
    """

    def __init__(
        self,
        factor: Factor,
        threshold: float = 0.0,
        buy_lag: int = 0,
        sell_lag: int = 0,
    ) -> None:
        self.factor = factor
        self.threshold = threshold
        self.buy_lag = buy_lag
        self.sell_lag = sell_lag

    def _compute_weights(
        self,
        symbols: list[str],
        prices: dict[str, PriceFrame],
        regime: RegimeSeries | None = None,
    ) -> pd.DataFrame:
        all_weights: dict[str, pd.Series] = {}

        for symbol in symbols:
            if symbol not in prices:
                continue

            price_frame = prices[symbol]
            full_index = price_frame.data.index

            # Compute factor, then reindex to the full price range.
            # Bars before the factor warm-up period become NaN → weight 0.
            factor_series = self.factor.compute(price_frame)
            values = factor_series.values.reindex(full_index)

            all_weights[symbol] = self._signal_to_weights(values)

        if not all_weights:
            return pd.DataFrame()

        return pd.DataFrame(all_weights).fillna(0.0)

    def _signal_to_weights(self, factor_values: pd.Series) -> pd.Series:
        """State machine: factor values → binary weights with confirmation lag.

        State transitions
        -----------------
        FLAT → CONFIRMING_ENTRY  : factor first crosses above threshold
        CONFIRMING_ENTRY → LONG  : buy_lag + 1 consecutive bars above threshold
        CONFIRMING_ENTRY → FLAT  : any bar below threshold resets counter
        LONG → CONFIRMING_EXIT   : factor first crosses below threshold
        CONFIRMING_EXIT → FLAT   : sell_lag + 1 consecutive bars below threshold
        CONFIRMING_EXIT → LONG   : any bar above threshold resets counter
        """
        weights = pd.Series(0.0, index=factor_values.index)
        in_position = False
        consec_above = 0  # consecutive confirming-entry bars
        consec_below = 0  # consecutive confirming-exit bars

        for i, v in enumerate(factor_values):
            # NaN = factor warm-up period; treat as "no signal", reset counters
            if pd.isna(v):
                consec_above = 0
                consec_below = 0
                weights.iloc[i] = 0.0
                continue

            above = v > self.threshold

            if not in_position:
                if above:
                    consec_above += 1
                    # Enter once we have buy_lag + 1 consecutive bars above
                    if consec_above >= self.buy_lag + 1:
                        in_position = True
                        consec_above = 0
                else:
                    consec_above = 0  # reversal resets — no memory of partial runs
            else:
                if not above:
                    consec_below += 1
                    # Exit once we have sell_lag + 1 consecutive bars below
                    if consec_below >= self.sell_lag + 1:
                        in_position = False
                        consec_below = 0
                else:
                    consec_below = 0  # recovery resets the exit countdown

            weights.iloc[i] = 1.0 if in_position else 0.0

        return weights
