"""Minimal strategy base class — compute only, no Streamlit."""
from abc import ABC, abstractmethod
from typing import Dict, Tuple

import pandas as pd


class BaseStrategy(ABC):
    DISPLAY_NAME: str = ""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def strategy_name(self) -> str:
        """Short file-safe name."""
        ...

    @abstractmethod
    def compute(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Returns (crossover_series, buy_signals, sell_signals)."""
        ...

    @abstractmethod
    def get_overlays(self, df: pd.DataFrame) -> Dict[str, pd.Series]:
        """Returns named price-level Series to overlay on price chart."""
        ...

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BaseStrategy):
            return NotImplemented
        return self.name == other.name
