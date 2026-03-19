"""Drawdown computation — MAE/MFE and max drawdown."""
from __future__ import annotations

from typing import List

import pandas as pd

from src.position.trade import Trade


def calculate_drawdown_during_trades(
    trades: List[Trade], price_series: pd.Series
) -> List[Trade]:
    """Fill mae_pct, mae_price, mfe_pct, mfe_price on each trade."""
    for trade in trades:
        start = trade.entry_date
        end = trade.exit_date if trade.exit_date is not None else price_series.index[-1]
        try:
            window = price_series.loc[start:end]
            if not window.empty:
                min_price = window.min()
                max_price = window.max()
                trade.mae_pct = (trade.entry_price - min_price) / trade.entry_price * 100
                trade.mae_price = float(min_price)
                trade.mfe_pct = (max_price - trade.entry_price) / trade.entry_price * 100
                trade.mfe_price = float(max_price)
        except Exception:
            pass
    return trades


def calculate_max_drawdown(price_series: pd.Series) -> float:
    """Max peak-to-trough drawdown of a price series. Returns negative %."""
    rolling_max = price_series.expanding().max()
    drawdown = (price_series - rolling_max) / rolling_max
    return float(drawdown.min()) * 100


def calculate_equity_curve_max_drawdown(trades: List[Trade]) -> float:
    """Max drawdown of the strategy equity curve built from closed trade returns. Returns negative %."""
    closed = [t for t in trades if t.status == "closed" and t.return_pct is not None]
    if not closed:
        return 0.0
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    for t in closed:
        equity *= (1 + t.return_pct / 100)
        if equity > peak:
            peak = equity
        dd = (equity - peak) / peak
        if dd < max_dd:
            max_dd = dd
    return max_dd * 100
