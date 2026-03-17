from abc import ABC, abstractmethod
from typing import Dict, Tuple

import numpy as np
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
    def get_overlays(self, df: pd.DataFrame) -> Dict[str, pd.Series]:
        """Returns named price-level Series to overlay on price chart."""
        ...

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BaseStrategy):
            return NotImplemented
        return self.name == other.name


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

    def get_overlays(self, df: pd.DataFrame) -> Dict[str, pd.Series]:
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

    def get_overlays(self, df: pd.DataFrame) -> Dict[str, pd.Series]:
        fast_ma = calculate_ma(df['Close'], self.fast_ma_type, self.fast_ma_length)
        slow_ma = calculate_ma(df['Close'], self.slow_ma_type, self.slow_ma_length)
        return {
            f"{self.fast_ma_type}({self.fast_ma_length})": fast_ma,
            f"{self.slow_ma_type}({self.slow_ma_length})": slow_ma,
        }


class DonchianBreakoutStrategy(BaseStrategy):
    def __init__(self, entry_length: int, exit_length: int):
        self.entry_length = entry_length
        self.exit_length = exit_length

    @property
    def name(self) -> str:
        return f"Donchian({self.entry_length}/{self.exit_length})"

    @property
    def strategy_name(self) -> str:
        return f"Donchian_{self.entry_length}_{self.exit_length}"

    def compute(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series, pd.Series]:
        close = df['Close']
        upper = df['High'].rolling(self.entry_length).max().shift(1)
        lower = df['Low'].rolling(self.exit_length).min().shift(1)

        buy = pd.Series(False, index=df.index)
        sell = pd.Series(False, index=df.index)
        in_trade = False

        for i in range(len(df)):
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

    def get_overlays(self, df: pd.DataFrame) -> Dict[str, pd.Series]:
        upper = df['High'].rolling(self.entry_length).max().shift(1)
        lower = df['Low'].rolling(self.exit_length).min().shift(1)
        return {
            f"Upper({self.entry_length})": upper,
            f"Lower({self.exit_length})": lower,
        }


class BollingerBandStrategy(BaseStrategy):
    def __init__(self, period: int, num_std_dev: float):
        self.period = period
        self.num_std_dev = num_std_dev

    @property
    def name(self) -> str:
        return f"BB({self.period}, {self.num_std_dev}σ)"

    @property
    def strategy_name(self) -> str:
        return f"BB_{self.period}_{str(self.num_std_dev).replace('.', '_')}"

    def _compute_bands(self, df: pd.DataFrame):
        close = df['Close']
        ma = calculate_ma(close, "SMA", self.period)
        std = close.rolling(self.period).std()
        upper = ma + std * self.num_std_dev
        lower = ma - std * self.num_std_dev
        return close, ma, upper, lower

    def compute(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series, pd.Series]:
        close, ma, upper, lower = self._compute_bands(df)

        buy = pd.Series(False, index=df.index)
        sell = pd.Series(False, index=df.index)
        in_trade = False

        for i in range(len(df)):
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

    def get_overlays(self, df: pd.DataFrame) -> Dict[str, pd.Series]:
        _, ma, upper, lower = self._compute_bands(df)
        return {
            f"BB Upper({self.period})": upper,
            f"SMA({self.period})": ma,
            f"BB Lower({self.period})": lower,
        }
