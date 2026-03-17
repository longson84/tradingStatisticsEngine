from typing import Dict, Tuple

import numpy as np
import pandas as pd
import streamlit as st

from src.indicators import moving_average
from src.strategy.strategies.base import BaseStrategy


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
        ma = moving_average(close, "SMA", self.period)
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
