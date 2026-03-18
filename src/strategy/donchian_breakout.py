"""Donchian Breakout strategy — delegates channel computation to indicators."""
from typing import Tuple

import numpy as np
import pandas as pd

from src.indicators.donchian import donchian_channels
from src.strategy.base import BaseStrategy


class DonchianBreakoutStrategy(BaseStrategy):
    DISPLAY_NAME = "Donchian Breakout"

    def __init__(self, entry_length: int, exit_length: int):
        self.entry_length = entry_length
        self.exit_length = exit_length

    @property
    def name(self) -> str:
        return f"Donchian({self.entry_length}/{self.exit_length})"

    @property
    def strategy_name(self) -> str:
        return f"Donchian_{self.entry_length}_{self.exit_length}"

    def compute(self, price: pd.DataFrame) -> Tuple[pd.Series, pd.Series, pd.Series]:
        close = price['Close']
        upper, lower = donchian_channels(price['High'], price['Low'], self.entry_length, self.exit_length)

        buy = pd.Series(False, index=price.index)
        sell = pd.Series(False, index=price.index)
        in_trade = False

        for i in range(len(price)):
            if np.isnan(upper.iloc[i]) or np.isnan(lower.iloc[i]):
                continue
            if not in_trade and close.iloc[i] > upper.iloc[i]:
                buy.iloc[i] = True
                in_trade = True
            elif in_trade and close.iloc[i] < lower.iloc[i]:
                sell.iloc[i] = True
                in_trade = False

        midline = (upper + lower) / 2
        crossover_series = ((close - midline) / midline).dropna()

        return crossover_series, buy, sell

