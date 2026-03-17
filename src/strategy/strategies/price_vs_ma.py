from typing import Dict, Tuple

import pandas as pd
import streamlit as st

from src.strategy.analytics import calculate_ma, generate_trade_signals
from src.strategy.strategies.base import BaseStrategy


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
