"""MA Crossover strategy."""
from typing import Tuple

import pandas as pd

from src.indicators.ma import moving_average
from src.strategy.strategy_utils import generate_trade_signals
from src.strategy.base import BaseStrategy


class MACrossoverStrategy(BaseStrategy):
    DISPLAY_NAME = "MA Crossover"

    def __init__(
        self,
        fast_ma_type: str,
        fast_ma_length: int,
        slow_ma_type: str,
        slow_ma_length: int,
        buy_lag: int,
        sell_lag: int,
    ):
        self.fast_ma_type = fast_ma_type
        self.fast_ma_length = fast_ma_length
        self.slow_ma_type = slow_ma_type
        self.slow_ma_length = slow_ma_length
        self.buy_lag = buy_lag
        self.sell_lag = sell_lag

    @property
    def name(self) -> str:
        fast = f"{self.fast_ma_type}({self.fast_ma_length})"
        slow = f"{self.slow_ma_type}({self.slow_ma_length})"
        return f"{fast} × {slow} — lag {self.buy_lag}/{self.sell_lag}"

    @property
    def strategy_name(self) -> str:
        return (
            f"MACross_{self.fast_ma_type}{self.fast_ma_length}"
            f"_{self.slow_ma_type}{self.slow_ma_length}"
            f"_lag{self.buy_lag}_{self.sell_lag}"
        )

    def compute(self, price: pd.DataFrame) -> Tuple[pd.Series, pd.Series, pd.Series]:
        fast_ma = moving_average(price['Close'], self.fast_ma_type, self.fast_ma_length)
        slow_ma = moving_average(price['Close'], self.slow_ma_type, self.slow_ma_length)
        crossover_series = (fast_ma - slow_ma).dropna()
        buy_signals, sell_signals = generate_trade_signals(
            price['Close'], crossover_series, self.buy_lag, self.sell_lag
        )
        return crossover_series, buy_signals, sell_signals

