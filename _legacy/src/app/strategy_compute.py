"""Cached strategy computation — shared across all strategy packs."""
from typing import Any, Dict, Optional

import pandas as pd
import streamlit as st

from src.shared.constants import INITIAL_CAPITAL
from src.strategy.base import BaseStrategy
from src.position import build_equity_curve, build_trades, get_current_position
from src.backtest import (
    calculate_drawdown_during_trades,
    calculate_equity_curve_max_drawdown,
    calculate_max_drawdown,
    calculate_trade_performance,
)


@st.cache_data(ttl=3600, show_spinner=False)
def compute_strategy(
    price: pd.DataFrame,
    _strategy: BaseStrategy,
    strategy_key: str,
    from_date: Optional[object] = None,
) -> Dict[str, Any]:
    """Pure computation — no Streamlit calls."""
    crossover_series, buy_signals, sell_signals = _strategy.compute(price)

    if from_date is not None:
        from_ts = pd.Timestamp(from_date)
        price = price[price.index >= from_ts]
        crossover_series = crossover_series[crossover_series.index >= from_ts]
        buy_signals = buy_signals[buy_signals.index >= from_ts]
        sell_signals = sell_signals[sell_signals.index >= from_ts]

    price = price["Close"]

    trades = build_trades(price, buy_signals, sell_signals)
    trades = calculate_drawdown_during_trades(trades, price)
    performance = calculate_trade_performance(trades)
    current_pos = get_current_position(price, crossover_series, buy_signals, sell_signals)
    bh_total_return = (float(price.iloc[-1]) / float(price.iloc[0]) - 1) * 100
    bh_max_drawdown = calculate_max_drawdown(price)
    strat_max_drawdown = calculate_equity_curve_max_drawdown(trades)

    strat_equity = build_equity_curve(price, buy_signals, sell_signals, INITIAL_CAPITAL)
    bh_equity = price / float(price.iloc[0]) * INITIAL_CAPITAL

    return {
        "price": price,
        "crossover_series": crossover_series,
        "trades": trades,
        "performance": performance,
        "current_position": current_pos,
        "strategy_label": strategy_key,
        "bh_total_return": bh_total_return,
        "bh_max_drawdown": bh_max_drawdown,
        "strat_max_drawdown": strat_max_drawdown,
        "strat_equity": strat_equity,
        "bh_equity": bh_equity,
    }
