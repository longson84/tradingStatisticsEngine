from typing import Dict, Tuple

import pandas as pd
import streamlit as st

from src.strategy.analytics import calculate_ma, generate_trade_signals
from src.strategy.strategies.base import BaseStrategy


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
