from typing import Dict, Tuple

import numpy as np
import pandas as pd
import streamlit as st

from src.strategy.analytics import generate_trade_signals
from src.strategy.strategies.base import BaseStrategy


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
