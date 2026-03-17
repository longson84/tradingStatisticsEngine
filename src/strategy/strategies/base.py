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
        """
        Returns:
            crossover_series — continuous signal that crosses zero
            buy_signals      — boolean Series, True on buy execution day
            sell_signals     — boolean Series, True on sell execution day
        """
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

    # ------------------------------------------------------------------
    # Registry hooks — override in each subclass
    # ------------------------------------------------------------------

    @classmethod
    def from_sidebar(cls, key_prefix: str) -> "BaseStrategy":
        """Render sidebar widgets and return a configured strategy instance."""
        raise NotImplementedError

    @classmethod
    def sweep_sidebar(cls, ticker: str, data_source: str) -> dict:
        """Render sweep sidebar widgets and return a config dict."""
        raise NotImplementedError

    @classmethod
    def build_from_sweep_config(cls, config: dict, length) -> "BaseStrategy":
        """Instantiate a strategy for one sweep length."""
        raise NotImplementedError

    @classmethod
    def sweep_label(cls, config: dict, length) -> str:
        """Short legend label for a sweep variant."""
        raise NotImplementedError

    @classmethod
    def should_skip_sweep_length(cls, config: dict, length) -> bool:
        """Return True to skip this length in the sweep (e.g. invalid fast/slow combo)."""
        return False
