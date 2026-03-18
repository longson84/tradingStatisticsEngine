"""Bollinger Bands strategy — delegates band computation to indicators."""
from typing import Tuple

import numpy as np
import pandas as pd

from src.indicators.bollinger import bollinger_bands
from src.strategy.base import BaseStrategy


class BollingerBandStrategy(BaseStrategy):
    DISPLAY_NAME = "Bollinger Bands"

    def __init__(self, period: int, num_std_dev: float):
        self.period = period
        self.num_std_dev = num_std_dev

    @property
    def name(self) -> str:
        return f"BB({self.period}, {self.num_std_dev}σ)"

    @property
    def strategy_name(self) -> str:
        return f"BB_{self.period}_{str(self.num_std_dev).replace('.', '_')}"

    def compute(self, price: pd.DataFrame) -> Tuple[pd.Series, pd.Series, pd.Series]:
        close = price['Close']
        ma, upper, lower = bollinger_bands(close, self.period, self.num_std_dev)

        buy = pd.Series(False, index=price.index)
        sell = pd.Series(False, index=price.index)
        in_trade = False

        for i in range(len(price)):
            if np.isnan(ma.iloc[i]):
                continue
            if not in_trade and close.iloc[i] < lower.iloc[i]:
                buy.iloc[i] = True
                in_trade = True
            elif in_trade and close.iloc[i] > ma.iloc[i]:
                sell.iloc[i] = True
                in_trade = False

        band_width = upper - lower
        crossover_series = ((close - ma) / band_width).dropna()

        return crossover_series, buy, sell

