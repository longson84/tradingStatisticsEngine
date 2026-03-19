"""Current position tracking."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

import pandas as pd

from src.position.engine import build_trades


@dataclass
class CurrentPosition:
    in_trade: bool
    entry_date: Optional[pd.Timestamp]
    entry_price: Optional[float]
    current_price: float
    days_held: Optional[int]
    unrealized_pnl_pct: Optional[float]
    crossover_value: float
    regime: Literal["above_zero", "below_zero"]


def get_current_position(
    price: pd.Series,
    crossover_series: pd.Series,
    buy_signals: pd.Series,
    sell_signals: pd.Series,
) -> CurrentPosition:
    current_price = float(price.iloc[-1])
    crossover_value = float(crossover_series.iloc[-1])
    regime: Literal["above_zero", "below_zero"] = (
        "above_zero" if crossover_value >= 0 else "below_zero"
    )

    trades = build_trades(price, buy_signals, sell_signals)
    open_trade = next((t for t in trades if t.status == "open"), None)

    if open_trade is not None:
        days_held = open_trade.holding_days
        unrealized = (current_price / open_trade.entry_price - 1) * 100
        return CurrentPosition(
            in_trade=True,
            entry_date=open_trade.entry_date,
            entry_price=open_trade.entry_price,
            current_price=current_price,
            days_held=days_held,
            unrealized_pnl_pct=unrealized,
            crossover_value=crossover_value,
            regime=regime,
        )
    else:
        return CurrentPosition(
            in_trade=False,
            entry_date=None,
            entry_price=None,
            current_price=current_price,
            days_held=None,
            unrealized_pnl_pct=None,
            crossover_value=crossover_value,
            regime=regime,
        )
