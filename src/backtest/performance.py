"""Trade performance statistics."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from src.position.trade import Trade


@dataclass
class TradePerformance:
    total_trades: int
    closed_trades: int
    open_trade: Optional[Trade]
    win_rate: float
    win_count: int
    loss_count: int
    avg_return: float
    avg_winning_return: float
    avg_losing_return: float
    best_trade_return: float
    worst_trade_return: float
    avg_holding_days: float
    max_consecutive_losses: int
    total_return: float


def calculate_trade_performance(trades: List[Trade]) -> TradePerformance:
    closed = [t for t in trades if t.status == "closed"]
    open_trade = next((t for t in trades if t.status == "open"), None)

    n_closed = len(closed)

    if n_closed == 0:
        return TradePerformance(
            total_trades=len(trades),
            closed_trades=0,
            open_trade=open_trade,
            win_rate=0.0,
            win_count=0,
            loss_count=0,
            avg_return=0.0,
            avg_winning_return=0.0,
            avg_losing_return=0.0,
            best_trade_return=0.0,
            worst_trade_return=0.0,
            avg_holding_days=0.0,
            max_consecutive_losses=0,
            total_return=0.0,
        )

    returns = [t.return_pct for t in closed if t.return_pct is not None]
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r <= 0]

    win_rate = len(wins) / n_closed * 100 if n_closed else 0.0
    avg_return = float(np.mean(returns)) if returns else 0.0
    avg_winning = float(np.mean(wins)) if wins else 0.0
    avg_losing = float(np.mean(losses)) if losses else 0.0
    best = float(max(returns)) if returns else 0.0
    worst = float(min(returns)) if returns else 0.0

    holding_days = [t.holding_days for t in closed if t.holding_days is not None]
    avg_holding = float(np.mean(holding_days)) if holding_days else 0.0

    max_consec_losses = 0
    consec = 0
    for r in returns:
        if r <= 0:
            consec += 1
            max_consec_losses = max(max_consec_losses, consec)
        else:
            consec = 0

    compound = 1.0
    for r in returns:
        compound *= (1 + r / 100)
    total_return = (compound - 1) * 100

    return TradePerformance(
        total_trades=len(trades),
        closed_trades=n_closed,
        open_trade=open_trade,
        win_rate=win_rate,
        win_count=len(wins),
        loss_count=len(losses),
        avg_return=avg_return,
        avg_winning_return=avg_winning,
        avg_losing_return=avg_losing,
        best_trade_return=best,
        worst_trade_return=worst,
        avg_holding_days=avg_holding,
        max_consecutive_losses=max_consec_losses,
        total_return=total_return,
    )
