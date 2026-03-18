"""Minimal strategy base class — compute only, no Streamlit."""
from abc import ABC, abstractmethod
from typing import Tuple

import pandas as pd


class BaseStrategy(ABC):
    DISPLAY_NAME: str = "" # Human-readable name for the Selector

    @property
    @abstractmethod
    def name(self) -> str: ... # Instance name for display, example: EMA(10) × SMA(50) — lag 1/1

    @property
    @abstractmethod
    def strategy_name(self) -> str:
        """Short file-safe name.""" # Instance name file-safe, example: MACross_EMA10_SMA50_lag1_1
        ...

    @abstractmethod
    def compute(self, price: pd.DataFrame) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Returns (crossover_series, buy_signals, sell_signals)."""
        ...

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BaseStrategy):
            return NotImplemented
        return self.name == other.name
