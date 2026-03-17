from abc import ABC, abstractmethod
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import streamlit as st

from src.strategy.analytics import calculate_ma, generate_trade_signals


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
        ma = calculate_ma(df['Close'], self.ma_type, self.ma_length)
        crossover_series = (df['Close'] / ma - 1).dropna()
        buy_signals, sell_signals = generate_trade_signals(
            df['Close'], crossover_series, self.buy_lag, self.sell_lag
        )
        return crossover_series, buy_signals, sell_signals

    def get_overlays(self, df: pd.DataFrame) -> Dict[str, pd.Series]:
        ma = calculate_ma(df['Close'], self.ma_type, self.ma_length)
        return {f"{self.ma_type}({self.ma_length})": ma}

    @classmethod
    def from_sidebar(cls, key_prefix: str) -> "PriceVsMAStrategy":
        col1, col2 = st.sidebar.columns(2)
        ma_type = col1.selectbox("MA Type:", ["SMA", "EMA", "WMA"], key=f"{key_prefix}_pma_type")
        ma_len = col2.number_input("MA Length:", min_value=2, value=50, step=10, key=f"{key_prefix}_pma_len")
        col3, col4 = st.sidebar.columns(2)
        buy_lag = col3.number_input("Buy Lag (days):", min_value=0, value=0, step=1, key=f"{key_prefix}_pma_buy_lag")
        sell_lag = col4.number_input("Sell Lag (days):", min_value=0, value=2, step=1, key=f"{key_prefix}_pma_sell_lag")
        return cls(ma_type, int(ma_len), int(buy_lag), int(sell_lag))

    @classmethod
    def sweep_sidebar(cls, ticker: str, data_source: str) -> dict:
        ma_type = st.sidebar.selectbox("MA Type:", ["SMA", "EMA", "WMA"], key="sweep_pma_type")
        col1, col2 = st.sidebar.columns(2)
        buy_lag = col1.number_input("Buy Lag (days):", min_value=0, value=0, step=1, key="sweep_pma_buy_lag")
        sell_lag = col2.number_input("Sell Lag (days):", min_value=0, value=2, step=1, key="sweep_pma_sell_lag")
        st.sidebar.markdown("**MA Length Sweep Range**")
        c1, c2, c3 = st.sidebar.columns(3)
        sweep_min = c1.number_input("Min", min_value=2, value=20, step=5, key="sweep_pma_min")
        sweep_max = c2.number_input("Max", min_value=2, value=200, step=5, key="sweep_pma_max")
        sweep_step = c3.number_input("Step", min_value=1, value=10, step=1, key="sweep_pma_step")
        return {
            "ticker": ticker, "data_source": data_source, "vnstock_source": "KBS",
            "strategy_type": cls.DISPLAY_NAME,
            "ma_type": ma_type, "buy_lag": int(buy_lag), "sell_lag": int(sell_lag),
            "sweep_lengths": list(range(int(sweep_min), int(sweep_max) + 1, int(sweep_step))),
        }

    @classmethod
    def build_from_sweep_config(cls, config: dict, length) -> "PriceVsMAStrategy":
        return cls(config["ma_type"], length, config["buy_lag"], config["sell_lag"])

    @classmethod
    def sweep_label(cls, config: dict, length) -> str:
        return f"{config['ma_type']}({length})"


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

    @classmethod
    def from_sidebar(cls, key_prefix: str) -> "MACrossoverStrategy":
        col1, col2 = st.sidebar.columns(2)
        fast_type = col1.selectbox("Fast MA Type:", ["EMA", "SMA", "WMA"], key=f"{key_prefix}_mac_fast_type")
        fast_len = col2.number_input("Fast Length:", min_value=2, value=50, step=10, key=f"{key_prefix}_mac_fast_len")
        col3, col4 = st.sidebar.columns(2)
        slow_type = col3.selectbox("Slow MA Type:", ["SMA", "EMA", "WMA"], key=f"{key_prefix}_mac_slow_type")
        slow_len = col4.number_input("Slow Length:", min_value=2, value=200, step=10, key=f"{key_prefix}_mac_slow_len")
        col5, col6 = st.sidebar.columns(2)
        buy_lag = col5.number_input("Buy Lag:", min_value=0, value=1, step=1, key=f"{key_prefix}_mac_buy_lag")
        sell_lag = col6.number_input("Sell Lag:", min_value=0, value=1, step=1, key=f"{key_prefix}_mac_sell_lag")
        return cls(fast_type, int(fast_len), slow_type, int(slow_len), int(buy_lag), int(sell_lag))

    @classmethod
    def sweep_sidebar(cls, ticker: str, data_source: str) -> dict:
        sweep_dim = st.sidebar.radio(
            "Sweep:", ["Fast Length", "Slow Length"], key="sweep_mac_dim", horizontal=True,
        )
        col1, col2 = st.sidebar.columns(2)
        fast_ma_type = col1.selectbox("Fast MA Type:", ["EMA", "SMA", "WMA"], key="sweep_mac_fast_type")
        slow_ma_type = col2.selectbox("Slow MA Type:", ["SMA", "EMA", "WMA"], key="sweep_mac_slow_type")
        col3, col4 = st.sidebar.columns(2)
        buy_lag = col3.number_input("Buy Lag:", min_value=0, value=1, step=1, key="sweep_mac_buy_lag")
        sell_lag = col4.number_input("Sell Lag:", min_value=0, value=1, step=1, key="sweep_mac_sell_lag")
        if sweep_dim == "Fast Length":
            st.sidebar.markdown("**Fast Length Sweep Range**")
            c1, c2, c3 = st.sidebar.columns(3)
            sweep_min = c1.number_input("Min", min_value=2, value=10, step=5, key="sweep_mac_fast_min")
            sweep_max = c2.number_input("Max", min_value=2, value=100, step=5, key="sweep_mac_fast_max")
            sweep_step = c3.number_input("Step", min_value=1, value=10, step=1, key="sweep_mac_fast_step")
            fixed_length = st.sidebar.number_input("Fixed Slow Length:", min_value=2, value=200, step=10, key="sweep_mac_slow_fixed")
        else:
            st.sidebar.markdown("**Slow Length Sweep Range**")
            c1, c2, c3 = st.sidebar.columns(3)
            sweep_min = c1.number_input("Min", min_value=2, value=100, step=10, key="sweep_mac_slow_min")
            sweep_max = c2.number_input("Max", min_value=2, value=300, step=10, key="sweep_mac_slow_max")
            sweep_step = c3.number_input("Step", min_value=1, value=20, step=1, key="sweep_mac_slow_step")
            fixed_length = st.sidebar.number_input("Fixed Fast Length:", min_value=2, value=50, step=10, key="sweep_mac_fast_fixed")
        return {
            "ticker": ticker, "data_source": data_source, "vnstock_source": "KBS",
            "strategy_type": cls.DISPLAY_NAME,
            "fast_ma_type": fast_ma_type, "slow_ma_type": slow_ma_type,
            "sweep_dimension": "fast" if sweep_dim == "Fast Length" else "slow",
            "fixed_length": int(fixed_length),
            "buy_lag": int(buy_lag), "sell_lag": int(sell_lag),
            "sweep_lengths": list(range(int(sweep_min), int(sweep_max) + 1, int(sweep_step))),
        }

    @classmethod
    def build_from_sweep_config(cls, config: dict, length) -> "MACrossoverStrategy":
        dim = config["sweep_dimension"]
        fast_len, slow_len = (length, config["fixed_length"]) if dim == "fast" else (config["fixed_length"], length)
        return cls(config["fast_ma_type"], fast_len, config["slow_ma_type"], slow_len, config["buy_lag"], config["sell_lag"])

    @classmethod
    def sweep_label(cls, config: dict, length) -> str:
        dim = config["sweep_dimension"]
        if dim == "fast":
            return f"{config['fast_ma_type']}({length})×{config['slow_ma_type']}({config['fixed_length']})"
        return f"{config['fast_ma_type']}({config['fixed_length']})×{config['slow_ma_type']}({length})"

    @classmethod
    def should_skip_sweep_length(cls, config: dict, length) -> bool:
        dim = config["sweep_dimension"]
        if dim == "fast":
            return length >= config["fixed_length"]
        return config["fixed_length"] >= length


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

    @classmethod
    def from_sidebar(cls, key_prefix: str) -> "DonchianBreakoutStrategy":
        col1, col2 = st.sidebar.columns(2)
        entry_len = col1.number_input("Entry Length:", min_value=2, value=20, step=5, key=f"{key_prefix}_don_entry")
        exit_len = col2.number_input("Exit Length:", min_value=2, value=10, step=5, key=f"{key_prefix}_don_exit")
        return cls(int(entry_len), int(exit_len))

    @classmethod
    def sweep_sidebar(cls, ticker: str, data_source: str) -> dict:
        sweep_dim = st.sidebar.radio(
            "Sweep:", ["Entry Length", "Exit Length"], key="sweep_don_dim", horizontal=True,
        )
        st.sidebar.markdown(f"**{sweep_dim} Sweep Range**")
        c1, c2, c3 = st.sidebar.columns(3)
        sweep_min = c1.number_input("Min", min_value=2, value=10, step=5, key="sweep_don_min")
        sweep_max = c2.number_input("Max", min_value=2, value=50, step=5, key="sweep_don_max")
        sweep_step = c3.number_input("Step", min_value=1, value=5, step=1, key="sweep_don_step")
        fixed_label = "Fixed Exit Length:" if sweep_dim == "Entry Length" else "Fixed Entry Length:"
        fixed_default = 10 if sweep_dim == "Entry Length" else 20
        fixed_length = st.sidebar.number_input(fixed_label, min_value=2, value=fixed_default, step=5, key="sweep_don_fixed")
        return {
            "ticker": ticker, "data_source": data_source, "vnstock_source": "KBS",
            "strategy_type": cls.DISPLAY_NAME,
            "sweep_dimension": "entry" if sweep_dim == "Entry Length" else "exit",
            "fixed_length": int(fixed_length),
            "sweep_lengths": list(range(int(sweep_min), int(sweep_max) + 1, int(sweep_step))),
        }

    @classmethod
    def build_from_sweep_config(cls, config: dict, length) -> "DonchianBreakoutStrategy":
        if config["sweep_dimension"] == "entry":
            return cls(length, config["fixed_length"])
        return cls(config["fixed_length"], length)

    @classmethod
    def sweep_label(cls, config: dict, length) -> str:
        if config["sweep_dimension"] == "entry":
            return f"Donchian({length}/{config['fixed_length']})"
        return f"Donchian({config['fixed_length']}/{length})"


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

    @classmethod
    def from_sidebar(cls, key_prefix: str) -> "BollingerBandStrategy":
        col1, col2 = st.sidebar.columns(2)
        bb_period = col1.number_input("Period:", min_value=5, value=20, step=1, key=f"{key_prefix}_bb_period")
        bb_std = col2.number_input("Std Dev:", min_value=0.5, value=2.0, step=0.25, format="%.2f", key=f"{key_prefix}_bb_std")
        return cls(int(bb_period), float(bb_std))

    @classmethod
    def sweep_sidebar(cls, ticker: str, data_source: str) -> dict:
        sweep_dim = st.sidebar.radio("Sweep:", ["Period", "Std Dev"], key="sweep_bb_dim", horizontal=True)
        if sweep_dim == "Period":
            st.sidebar.markdown("**Period Sweep Range**")
            c1, c2, c3 = st.sidebar.columns(3)
            sweep_min = c1.number_input("Min", min_value=5, value=10, step=5, key="sweep_bb_period_min")
            sweep_max = c2.number_input("Max", min_value=5, value=40, step=5, key="sweep_bb_period_max")
            sweep_step = c3.number_input("Step", min_value=1, value=5, step=1, key="sweep_bb_period_step")
            fixed_std = st.sidebar.number_input("Fixed Std Dev:", min_value=0.5, value=2.0, step=0.25, format="%.2f", key="sweep_bb_std_fixed")
            return {
                "ticker": ticker, "data_source": data_source, "vnstock_source": "KBS",
                "strategy_type": cls.DISPLAY_NAME,
                "sweep_dimension": "period", "fixed_value": float(fixed_std),
                "sweep_lengths": list(range(int(sweep_min), int(sweep_max) + 1, int(sweep_step))),
            }
        else:
            st.sidebar.markdown("**Std Dev Sweep Range**")
            c1, c2, c3 = st.sidebar.columns(3)
            sweep_min = c1.number_input("Min", min_value=0.5, value=1.0, step=0.25, format="%.2f", key="sweep_bb_std_min")
            sweep_max = c2.number_input("Max", min_value=0.5, value=3.0, step=0.25, format="%.2f", key="sweep_bb_std_max")
            sweep_step = c3.number_input("Step", min_value=0.25, value=0.25, step=0.25, format="%.2f", key="sweep_bb_std_step")
            fixed_period = st.sidebar.number_input("Fixed Period:", min_value=5, value=20, step=1, key="sweep_bb_period_fixed")
            return {
                "ticker": ticker, "data_source": data_source, "vnstock_source": "KBS",
                "strategy_type": cls.DISPLAY_NAME,
                "sweep_dimension": "std_dev", "fixed_value": int(fixed_period),
                "sweep_lengths": list(np.arange(float(sweep_min), float(sweep_max) + float(sweep_step) / 2, float(sweep_step))),
            }

    @classmethod
    def build_from_sweep_config(cls, config: dict, length) -> "BollingerBandStrategy":
        if config["sweep_dimension"] == "period":
            return cls(int(length), config["fixed_value"])
        return cls(config["fixed_value"], float(length))

    @classmethod
    def sweep_label(cls, config: dict, length) -> str:
        if config["sweep_dimension"] == "period":
            return f"BB({length}, {config['fixed_value']}σ)"
        return f"BB({config['fixed_value']}, {length}σ)"


# ---------------------------------------------------------------------------
# Registry — add new strategies here only
# ---------------------------------------------------------------------------

STRATEGY_REGISTRY: dict[str, type[BaseStrategy]] = {
    cls.DISPLAY_NAME: cls
    for cls in [PriceVsMAStrategy, MACrossoverStrategy, DonchianBreakoutStrategy, BollingerBandStrategy]
}

STRATEGY_NAMES: List[str] = list(STRATEGY_REGISTRY)
