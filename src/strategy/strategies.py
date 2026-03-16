from abc import ABC, abstractmethod
from typing import Dict, Tuple

import pandas as pd

from src.strategy.analytics import calculate_ma, generate_trade_signals


class BaseStrategy(ABC):
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
    def get_ma_overlays(self, df: pd.DataFrame) -> Dict[str, pd.Series]:
        """Returns MA series to overlay on price chart."""
        ...


class PriceVsMAStrategy(BaseStrategy):
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
        ma = calculate_ma(df['Close'], self.ma_type, self.ma_length)
        crossover_series = (df['Close'] / ma - 1).dropna()
        buy_signals, sell_signals = generate_trade_signals(
            df['Close'], crossover_series, self.buy_lag, self.sell_lag
        )
        return crossover_series, buy_signals, sell_signals

    def get_ma_overlays(self, df: pd.DataFrame) -> Dict[str, pd.Series]:
        ma = calculate_ma(df['Close'], self.ma_type, self.ma_length)
        return {f"{self.ma_type}({self.ma_length})": ma}


class MACrossoverStrategy(BaseStrategy):
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

    def compute(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series, pd.Series]:
        fast_ma = calculate_ma(df['Close'], self.fast_ma_type, self.fast_ma_length)
        slow_ma = calculate_ma(df['Close'], self.slow_ma_type, self.slow_ma_length)
        crossover_series = (fast_ma - slow_ma).dropna()
        buy_signals, sell_signals = generate_trade_signals(
            df['Close'], crossover_series, self.buy_lag, self.sell_lag
        )
        return crossover_series, buy_signals, sell_signals

    def get_ma_overlays(self, df: pd.DataFrame) -> Dict[str, pd.Series]:
        fast_ma = calculate_ma(df['Close'], self.fast_ma_type, self.fast_ma_length)
        slow_ma = calculate_ma(df['Close'], self.slow_ma_type, self.slow_ma_length)
        return {
            f"{self.fast_ma_type}({self.fast_ma_length})": fast_ma,
            f"{self.slow_ma_type}({self.slow_ma_length})": slow_ma,
        }
