"""MA Crossover strategy — go long when fast MA > slow MA."""
from __future__ import annotations

from typing import Literal

import pandas as pd

from trading_engine.types import PriceFrame, RegimeSeries
from trading_engine.strategy.base import BaseStrategy
from trading_engine.factors.moving_average import MaType, compute_ma


class MACrossover(BaseStrategy):
    """Long-only MA crossover strategy.

    Weight = 1.0 when fast MA > slow MA, 0.0 otherwise.
    Supports configurable MA types and lag.
    """

    def __init__(
        self,
        fast_ma_type: MaType = "EMA",
        fast_length: int = 10,
        slow_ma_type: MaType = "SMA",
        slow_length: int = 50,
        buy_lag: int = 1,
        sell_lag: int = 1,
    ):
        self.fast_ma_type = fast_ma_type
        self.fast_length = fast_length
        self.slow_ma_type = slow_ma_type
        self.slow_length = slow_length
        self.buy_lag = buy_lag
        self.sell_lag = sell_lag

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

            close = prices[symbol].data["close"]
            fast = compute_ma(close, self.fast_ma_type, self.fast_length)
            slow = compute_ma(close, self.slow_ma_type, self.slow_length)

            # Raw signal: 1 when fast > slow
            raw_signal = (fast > slow).astype(float)

            # Apply lag: shift signal forward by buy_lag/sell_lag days
            # Buy signal = transition from 0 -> 1, lagged by buy_lag
            # Sell signal = transition from 1 -> 0, lagged by sell_lag
            weights = _apply_lag(raw_signal, self.buy_lag, self.sell_lag)

            all_weights[symbol] = weights

        if not all_weights:
            return pd.DataFrame()

        result = pd.DataFrame(all_weights).fillna(0.0)
        return result


def _apply_lag(signal: pd.Series, buy_lag: int, sell_lag: int) -> pd.Series:
    """Apply entry/exit lag to a binary signal series.

    When signal transitions from 0 -> 1, delay the entry by buy_lag bars.
    When signal transitions from 1 -> 0, delay the exit by sell_lag bars.
    """
    if buy_lag == 0 and sell_lag == 0:
        return signal

    result = pd.Series(0.0, index=signal.index)
    in_position = False
    lag_counter = 0
    pending: str | None = None  # "buy" or "sell"

    for i in range(len(signal)):
        raw = float(signal.iloc[i])

        if pending == "buy":
            lag_counter -= 1
            if lag_counter <= 0:
                in_position = True
                pending = None
        elif pending == "sell":
            lag_counter -= 1
            if lag_counter <= 0:
                in_position = False
                pending = None

        # Detect transitions
        prev_raw = float(signal.iloc[i - 1]) if i > 0 else 0.0
        if raw == 1.0 and prev_raw == 0.0 and not in_position and pending != "buy":
            if buy_lag == 0:
                in_position = True
            else:
                pending = "buy"
                lag_counter = buy_lag
        elif raw == 0.0 and prev_raw == 1.0 and in_position and pending != "sell":
            if sell_lag == 0:
                in_position = False
            else:
                pending = "sell"
                lag_counter = sell_lag

        result.iloc[i] = 1.0 if in_position else 0.0

    return result
