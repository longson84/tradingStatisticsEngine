"""Pure trade analytics — zero Streamlit dependencies."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional, Tuple

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# MA Computation
# ---------------------------------------------------------------------------

def calculate_ma(series: pd.Series, ma_type: Literal["SMA", "EMA", "WMA"], length: int) -> pd.Series:
    if ma_type == "SMA":
        return series.rolling(length).mean()
    elif ma_type == "EMA":
        return series.ewm(span=length, adjust=False).mean()
    elif ma_type == "WMA":
        weights = np.arange(1, length + 1, dtype=float)
        weights /= weights.sum()

        def _wma(x):
            return np.dot(x, weights)

        return series.rolling(length).apply(_wma, raw=True)
    else:
        raise ValueError(f"Unknown MA type: {ma_type}")


# ---------------------------------------------------------------------------
# Signal Generation
# ---------------------------------------------------------------------------

def generate_trade_signals(
    price: pd.Series,
    crossover_series: pd.Series,
    buy_lag: int,
    sell_lag: int,
) -> Tuple[pd.Series, pd.Series]:
    """
    Detect zero-crossings in crossover_series and schedule buy/sell signals
    after the respective lag.

    Returns:
        buy_signals  — boolean Series aligned to price index
        sell_signals — boolean Series aligned to price index
    """
    common_idx = price.index.intersection(crossover_series.index)
    cross = crossover_series.reindex(common_idx)

    buy_signals = pd.Series(False, index=common_idx)
    sell_signals = pd.Series(False, index=common_idx)

    prev_sign = np.sign(cross.iloc[0]) if len(cross) > 0 else 0

    for i in range(1, len(common_idx)):
        cur_sign = np.sign(cross.iloc[i])

        if prev_sign < 0 and cur_sign >= 0:
            # Price crossed above MA → schedule BUY after buy_lag days
            # Only execute if price is still above MA on that day (confirmation)
            target_i = i + buy_lag
            if target_i < len(common_idx):
                if np.sign(cross.iloc[target_i]) >= 0:
                    buy_signals.iloc[target_i] = True

        elif prev_sign > 0 and cur_sign <= 0:
            # Price crossed below MA → schedule SELL after sell_lag days
            # Only execute if price is still below MA on that day (confirmation)
            # If price recovered above MA by then, skip — trade continues
            target_i = i + sell_lag
            if target_i < len(common_idx):
                if np.sign(cross.iloc[target_i]) <= 0:
                    sell_signals.iloc[target_i] = True

        if cur_sign != 0:
            prev_sign = cur_sign

    return buy_signals, sell_signals


# ---------------------------------------------------------------------------
# Trade Dataclass
# ---------------------------------------------------------------------------

@dataclass
class Trade:
    entry_date: pd.Timestamp
    entry_price: float
    exit_date: Optional[pd.Timestamp]
    exit_price: Optional[float]
    return_pct: Optional[float]        # (exit/entry - 1) * 100
    holding_days: Optional[int]        # trading days
    status: Literal["closed", "open"]
    mae_pct: Optional[float] = None    # filled by calculate_drawdown_during_trades
    mae_price: Optional[float] = None  # price at MAE (lowest price during trade)
    mfe_pct: Optional[float] = None    # Maximum Favorable Excursion — peak return during trade
    mfe_price: Optional[float] = None  # price at MFE (highest price during trade)
    equity_at_close: Optional[float] = None  # strategy capital after this trade closes (stamped by _compute_ticker_core)


# ---------------------------------------------------------------------------
# Trade Construction
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Drawdown During Trades (MAE) and Peak Return (MFE)
# ---------------------------------------------------------------------------

def calculate_drawdown_during_trades(
    trades: List[Trade], price_series: pd.Series
) -> List[Trade]:
    """Fill mae_pct and mfe_pct on each trade."""
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


# ---------------------------------------------------------------------------
# Performance Dataclass + Calculation
# ---------------------------------------------------------------------------

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

    # Max consecutive losses
    max_consec_losses = 0
    consec = 0
    for r in returns:
        if r <= 0:
            consec += 1
            max_consec_losses = max(max_consec_losses, consec)
        else:
            consec = 0

    # Total return (compound)
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


# ---------------------------------------------------------------------------
# Equity Curve
# ---------------------------------------------------------------------------

def build_equity_curve(
    price: pd.Series,
    buy_signals: pd.Series,
    sell_signals: pd.Series,
    initial: float = 1000.0,
) -> pd.Series:
    """
    Simulate the strategy equity curve starting from `initial` capital.
    - In a trade: equity tracks price proportionally from entry.
    - Out of a trade: equity stays flat (cash).
    """
    equity = pd.Series(index=price.index, dtype=float)
    current_equity = initial
    in_trade = False
    entry_price: Optional[float] = None
    entry_equity: Optional[float] = None

    for i, date in enumerate(price.index):
        p = float(price.iloc[i])

        # Process SELL before BUY so that on days where both fire (e.g. buy_lag=0,
        # sell_lag=2 and a cross happens exactly 2 days after a death cross), the old
        # trade is closed first and the new entry can open on the same bar.
        if sell_signals.get(date, False) and in_trade and entry_price:
            current_equity = entry_equity * (p / entry_price)
            in_trade = False
            entry_price = None
            entry_equity = None

        if buy_signals.get(date, False) and not in_trade:
            in_trade = True
            entry_price = p
            entry_equity = current_equity

        equity.iloc[i] = (entry_equity * (p / entry_price)) if (in_trade and entry_price) else current_equity

    return equity


# ---------------------------------------------------------------------------
# Buy & Hold + Equity Curve Stats
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Current Position
# ---------------------------------------------------------------------------

@dataclass
class CurrentPosition:
    in_trade: bool
    entry_date: Optional[pd.Timestamp]
    entry_price: Optional[float]
    current_price: float
    days_held: Optional[int]
    unrealized_pnl_pct: Optional[float]
    current_signal_value: float
    regime: Literal["above_zero", "below_zero"]


def get_current_position(
    price: pd.Series,
    crossover_series: pd.Series,
    buy_signals: pd.Series,
    sell_signals: pd.Series,
) -> CurrentPosition:
    current_price = float(price.iloc[-1])
    current_signal = float(crossover_series.iloc[-1])
    regime: Literal["above_zero", "below_zero"] = (
        "above_zero" if current_signal >= 0 else "below_zero"
    )

    # Replay trades to find if currently in a trade
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
            current_signal_value=current_signal,
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
            current_signal_value=current_signal,
            regime=regime,
        )
