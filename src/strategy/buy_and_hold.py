"""Buy and Hold strategy — buys day 1, never sells. Used as benchmark."""
from typing import Dict, Tuple

import pandas as pd

from src.strategy.base import BaseStrategy


class BuyAndHoldStrategy(BaseStrategy):
    DISPLAY_NAME = "Buy & Hold"

    @property
    def name(self) -> str:
        return "Buy & Hold"

    @property
    def strategy_name(self) -> str:
        return "BuyAndHold"

    def compute(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series, pd.Series]:
        close = df['Close']

        buy_signals = pd.Series(False, index=df.index)
        sell_signals = pd.Series(False, index=df.index)

        # Buy on the first valid bar
        buy_signals.iloc[0] = True

        # Crossover is always positive (always in position)
        crossover_series = pd.Series(1.0, index=df.index)

        return crossover_series, buy_signals, sell_signals

    def get_overlays(self, df: pd.DataFrame) -> Dict[str, pd.Series]:
        return {}
