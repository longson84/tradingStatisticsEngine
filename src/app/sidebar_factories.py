"""Strategy sidebar factories — extracted from strategy classes. All Streamlit code."""
import numpy as np
import streamlit as st

from src.strategy.price_vs_ma import PriceVsMAStrategy
from src.strategy.ma_crossover import MACrossoverStrategy
from src.strategy.bollinger_bands import BollingerBandStrategy
from src.strategy.donchian_breakout import DonchianBreakoutStrategy
from src.indicators.definitions.distance_from_peak import DistanceFromPeakIndicator
from src.indicators.definitions.ahr999 import AHR999Indicator
from src.indicators.definitions.ma_ratio import MARatioIndicator


# ---------------------------------------------------------------------------
# Strategy sidebar factories
# ---------------------------------------------------------------------------

def price_vs_ma_from_sidebar(key_prefix: str) -> PriceVsMAStrategy:
    col1, col2 = st.sidebar.columns(2)
    ma_type = col1.selectbox("MA Type:", ["SMA", "EMA", "WMA"], key=f"{key_prefix}_pma_type")
    ma_len = col2.number_input("MA Length:", min_value=2, value=50, step=10, key=f"{key_prefix}_pma_len")
    col3, col4 = st.sidebar.columns(2)
    buy_lag = col3.number_input("Buy Lag (days):", min_value=0, value=0, step=1, key=f"{key_prefix}_pma_buy_lag")
    sell_lag = col4.number_input("Sell Lag (days):", min_value=0, value=2, step=1, key=f"{key_prefix}_pma_sell_lag")
    return PriceVsMAStrategy(ma_type, int(ma_len), int(buy_lag), int(sell_lag))


def ma_crossover_from_sidebar(key_prefix: str) -> MACrossoverStrategy:
    col1, col2 = st.sidebar.columns(2)
    fast_type = col1.selectbox("Fast MA Type:", ["EMA", "SMA", "WMA"], key=f"{key_prefix}_mac_fast_type")
    fast_len = col2.number_input("Fast Length:", min_value=2, value=50, step=10, key=f"{key_prefix}_mac_fast_len")
    col3, col4 = st.sidebar.columns(2)
    slow_type = col3.selectbox("Slow MA Type:", ["SMA", "EMA", "WMA"], key=f"{key_prefix}_mac_slow_type")
    slow_len = col4.number_input("Slow Length:", min_value=2, value=200, step=10, key=f"{key_prefix}_mac_slow_len")
    col5, col6 = st.sidebar.columns(2)
    buy_lag = col5.number_input("Buy Lag:", min_value=0, value=1, step=1, key=f"{key_prefix}_mac_buy_lag")
    sell_lag = col6.number_input("Sell Lag:", min_value=0, value=1, step=1, key=f"{key_prefix}_mac_sell_lag")
    return MACrossoverStrategy(fast_type, int(fast_len), slow_type, int(slow_len), int(buy_lag), int(sell_lag))


def bollinger_from_sidebar(key_prefix: str) -> BollingerBandStrategy:
    col1, col2 = st.sidebar.columns(2)
    bb_period = col1.number_input("Period:", min_value=5, value=20, step=1, key=f"{key_prefix}_bb_period")
    bb_std = col2.number_input("Std Dev:", min_value=0.5, value=2.0, step=0.25, format="%.2f", key=f"{key_prefix}_bb_std")
    return BollingerBandStrategy(int(bb_period), float(bb_std))


def donchian_from_sidebar(key_prefix: str) -> DonchianBreakoutStrategy:
    col1, col2 = st.sidebar.columns(2)
    entry_len = col1.number_input("Entry Length:", min_value=2, value=20, step=5, key=f"{key_prefix}_don_entry")
    exit_len = col2.number_input("Exit Length:", min_value=2, value=10, step=5, key=f"{key_prefix}_don_exit")
    return DonchianBreakoutStrategy(int(entry_len), int(exit_len))


SIDEBAR_REGISTRY = {
    "Price vs MA": price_vs_ma_from_sidebar,
    "MA Crossover": ma_crossover_from_sidebar,
    "Bollinger Bands": bollinger_from_sidebar,
    "Donchian Breakout": donchian_from_sidebar,
}


# ---------------------------------------------------------------------------
# Sweep sidebar factories
# ---------------------------------------------------------------------------

def price_vs_ma_sweep_sidebar(ticker: str, data_source: str) -> dict:
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
        "strategy_type": "Price vs MA",
        "ma_type": ma_type, "buy_lag": int(buy_lag), "sell_lag": int(sell_lag),
        "sweep_lengths": list(range(int(sweep_min), int(sweep_max) + 1, int(sweep_step))),
    }


def ma_crossover_sweep_sidebar(ticker: str, data_source: str) -> dict:
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
        "strategy_type": "MA Crossover",
        "fast_ma_type": fast_ma_type, "slow_ma_type": slow_ma_type,
        "sweep_dimension": "fast" if sweep_dim == "Fast Length" else "slow",
        "fixed_length": int(fixed_length),
        "buy_lag": int(buy_lag), "sell_lag": int(sell_lag),
        "sweep_lengths": list(range(int(sweep_min), int(sweep_max) + 1, int(sweep_step))),
    }


def bollinger_sweep_sidebar(ticker: str, data_source: str) -> dict:
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
            "strategy_type": "Bollinger Bands",
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
            "strategy_type": "Bollinger Bands",
            "sweep_dimension": "std_dev", "fixed_value": int(fixed_period),
            "sweep_lengths": list(np.arange(float(sweep_min), float(sweep_max) + float(sweep_step) / 2, float(sweep_step))),
        }


def donchian_sweep_sidebar(ticker: str, data_source: str) -> dict:
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
        "strategy_type": "Donchian Breakout",
        "sweep_dimension": "entry" if sweep_dim == "Entry Length" else "exit",
        "fixed_length": int(fixed_length),
        "sweep_lengths": list(range(int(sweep_min), int(sweep_max) + 1, int(sweep_step))),
    }


SWEEP_SIDEBAR_REGISTRY = {
    "Price vs MA": price_vs_ma_sweep_sidebar,
    "MA Crossover": ma_crossover_sweep_sidebar,
    "Bollinger Bands": bollinger_sweep_sidebar,
    "Donchian Breakout": donchian_sweep_sidebar,
}


# ---------------------------------------------------------------------------
# Sweep build/label/skip helpers
# ---------------------------------------------------------------------------

def build_from_sweep_config(strategy_type: str, config: dict, length):
    """Build a strategy instance for one sweep length."""
    if strategy_type == "Price vs MA":
        return PriceVsMAStrategy(config["ma_type"], length, config["buy_lag"], config["sell_lag"])
    elif strategy_type == "MA Crossover":
        dim = config["sweep_dimension"]
        fast_len, slow_len = (length, config["fixed_length"]) if dim == "fast" else (config["fixed_length"], length)
        return MACrossoverStrategy(config["fast_ma_type"], fast_len, config["slow_ma_type"], slow_len, config["buy_lag"], config["sell_lag"])
    elif strategy_type == "Bollinger Bands":
        if config["sweep_dimension"] == "period":
            return BollingerBandStrategy(int(length), config["fixed_value"])
        return BollingerBandStrategy(config["fixed_value"], float(length))
    elif strategy_type == "Donchian Breakout":
        if config["sweep_dimension"] == "entry":
            return DonchianBreakoutStrategy(length, config["fixed_length"])
        return DonchianBreakoutStrategy(config["fixed_length"], length)
    raise ValueError(f"Unknown strategy type: {strategy_type}")


def sweep_label(strategy_type: str, config: dict, length) -> str:
    """Short legend label for a sweep variant."""
    if strategy_type == "Price vs MA":
        return f"{config['ma_type']}({length})"
    elif strategy_type == "MA Crossover":
        dim = config["sweep_dimension"]
        if dim == "fast":
            return f"{config['fast_ma_type']}({length})×{config['slow_ma_type']}({config['fixed_length']})"
        return f"{config['fast_ma_type']}({config['fixed_length']})×{config['slow_ma_type']}({length})"
    elif strategy_type == "Bollinger Bands":
        if config["sweep_dimension"] == "period":
            return f"BB({length}, {config['fixed_value']}σ)"
        return f"BB({config['fixed_value']}, {length}σ)"
    elif strategy_type == "Donchian Breakout":
        if config["sweep_dimension"] == "entry":
            return f"Donchian({length}/{config['fixed_length']})"
        return f"Donchian({config['fixed_length']}/{length})"
    return str(length)


def should_skip_sweep_length(strategy_type: str, config: dict, length) -> bool:
    """Return True to skip this length (e.g. invalid fast/slow combo)."""
    if strategy_type == "MA Crossover":
        dim = config["sweep_dimension"]
        if dim == "fast":
            return length >= config["fixed_length"]
        return config["fixed_length"] >= length
    return False
