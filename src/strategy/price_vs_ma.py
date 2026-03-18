"""Price vs MA strategy."""
from typing import Dict, Tuple

import pandas as pd

from src.indicators.functions.ma import moving_average
from src.strategy.signal_utils import generate_trade_signals
from src.strategy.base import BaseStrategy


class PriceVsMAStrategy(BaseStrategy):
    DISPLAY_NAME = "Price vs MA"

    def __init__(self, ma_type: str, ma_length: int, buy_lag: int, sell_lag: int):
        self.ma_type = ma_type
        self.ma_length = ma_length
        self.buy_lag = buy_lag
        self.sell_lag = sell_lag

    @property
    def name(self) -> str:
        return f"Price vs {self.ma_type}({self.ma_length}) — lag {self.buy_lag}/{self.sell_lag}"

    @property
    def strategy_name(self) -> str:
        return f"PriceVsMA_{self.ma_type}{self.ma_length}_lag{self.buy_lag}_{self.sell_lag}"

    def compute(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series, pd.Series]:
        ma = moving_average(df['Close'], self.ma_type, self.ma_length)
        crossover_series = (df['Close'] / ma - 1).dropna()
        buy_signals, sell_signals = generate_trade_signals(
            df['Close'], crossover_series, self.buy_lag, self.sell_lag
        )
        return crossover_series, buy_signals, sell_signals

    def get_overlays(self, df: pd.DataFrame) -> Dict[str, pd.Series]:
        ma = moving_average(df['Close'], self.ma_type, self.ma_length)
        return {f"{self.ma_type}({self.ma_length})": ma}
