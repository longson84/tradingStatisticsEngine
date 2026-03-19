"""Trade construction and equity curve simulation."""
from __future__ import annotations

from typing import List, Optional

import pandas as pd

from src.position.trade import Trade


def build_trades(
    price: pd.Series,
    buy_signals: pd.Series,
    sell_signals: pd.Series,
) -> List[Trade]:
    trades: List[Trade] = []
    open_trade: Optional[Trade] = None

    common_idx = price.index

    for i, date in enumerate(common_idx):
        p = price.iloc[i]

        # SELL before BUY: same-day close+reopen works correctly
        if sell_signals.get(date, False) and open_trade is not None:
            holding = i - common_idx.get_loc(open_trade.entry_date)
            ret = (p / open_trade.entry_price - 1) * 100
            open_trade.exit_date = date
            open_trade.exit_price = p
            open_trade.return_pct = ret
            open_trade.holding_days = holding
            open_trade.status = "closed"
            trades.append(open_trade)
            open_trade = None

        if buy_signals.get(date, False) and open_trade is None:
            open_trade = Trade(
                entry_date=date,
                entry_price=p,
                exit_date=None,
                exit_price=None,
                return_pct=None,
                holding_days=None,
                status="open",
            )

    # Emit open trade if any
    if open_trade is not None:
        last_price = price.iloc[-1]
        last_i = len(common_idx) - 1
        holding = last_i - common_idx.get_loc(open_trade.entry_date)
        open_trade.exit_price = last_price
        open_trade.return_pct = (last_price / open_trade.entry_price - 1) * 100
        open_trade.holding_days = holding
        trades.append(open_trade)

    return trades


def build_equity_curve(
    price: pd.Series,
    buy_signals: pd.Series,
    sell_signals: pd.Series,
    initial: float = 1000.0,
) -> pd.Series:
    """Simulate the strategy equity curve starting from `initial` capital."""
    equity = pd.Series(index=price.index, dtype=float)
    current_equity = initial
    in_trade: bool = False
    entry_price: Optional[float] = None
    entry_equity: Optional[float] = None

    for i, date in enumerate(price.index):
        p = float(price.iloc[i])

        if sell_signals.get(date, False) and in_trade and entry_price:
            current_equity = entry_equity * (p / entry_price)
            in_trade = False

        if buy_signals.get(date, False) and not in_trade:
            in_trade = True
            entry_price = p
            entry_equity = current_equity

        equity.iloc[i] = (entry_equity * (p / entry_price)) if (in_trade and entry_price) else current_equity

    return equity
