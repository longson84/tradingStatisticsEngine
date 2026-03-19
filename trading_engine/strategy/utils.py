"""Strategy utilities — weight-to-trade conversion.

The core function weight_transitions_to_trades() converts a weight matrix
into a list of Trade records. Called automatically by BaseStrategy.compute().

Zero-crossing rule:
  weight 0.5 -> -0.3 produces 2 Trade records (exit long + enter short)
  atomically in the same bar.

Partial weight changes:
  weight 0.5 -> 0.3 (same direction, non-zero) appends a WeightEvent
  to the existing trade's weight_history — no new Trade record.
"""
from __future__ import annotations

import math
from datetime import date as date_type

import numpy as np
import pandas as pd

from trading_engine.types import PriceFrame, StrategyOutputError, Trade, WeightEvent


def weight_transitions_to_trades(
    weights: pd.DataFrame,
    prices: dict[str, PriceFrame],
) -> list[Trade]:
    """Convert a weight matrix into Trade records.

    Args:
        weights: DataFrame of shape (time x symbols), values in [-1, 1].
        prices: Dict mapping symbol -> PriceFrame for close prices.

    Returns:
        List of Trade records representing all positions.

    Raises:
        StrategyOutputError: If weights contain NaN values.
    """
    if weights.isna().any().any():
        nan_locs = weights.isna().stack()
        first_nan = nan_locs[nan_locs].index[0]
        raise StrategyOutputError(
            f"Weight matrix contains NaN at date={first_nan[0]}, "
            f"symbol={first_nan[1]}. NaN weights are never allowed."
        )

    trades: list[Trade] = []

    for symbol in weights.columns:
        if symbol not in prices:
            continue

        close = prices[symbol].data["close"]
        symbol_weights = weights[symbol]

        # Align weight dates with available price dates
        common_dates = symbol_weights.index.intersection(close.index)
        if common_dates.empty:
            continue

        symbol_weights = symbol_weights.loc[common_dates]
        close = close.loc[common_dates]

        open_trade: Trade | None = None

        for i, dt in enumerate(common_dates):
            w = float(symbol_weights.iloc[i])
            p = float(close.iloc[i])
            prev_w = float(symbol_weights.iloc[i - 1]) if i > 0 else 0.0

            d = _to_date(dt)

            # No change
            if w == prev_w:
                continue

            # Determine if this is a zero-crossing (direction change)
            crosses_zero = (prev_w > 0 and w < 0) or (prev_w < 0 and w > 0)

            if crosses_zero:
                # Atomic: close existing trade, then open new one
                if open_trade is not None:
                    open_trade = _close_trade(open_trade, d, p, close, common_dates)
                    trades.append(open_trade)
                    open_trade = None

                # Open new trade in opposite direction
                direction = "long" if w > 0 else "short"
                open_trade = Trade(
                    symbol=symbol,
                    direction=direction,
                    entry_date=d,
                    entry_price=p,
                    entry_weight=w,
                    weight_history=[WeightEvent(date=d, weight=w, price=p)],
                )

            elif prev_w == 0 and w != 0:
                # New position from flat
                direction = "long" if w > 0 else "short"
                open_trade = Trade(
                    symbol=symbol,
                    direction=direction,
                    entry_date=d,
                    entry_price=p,
                    entry_weight=w,
                    weight_history=[WeightEvent(date=d, weight=w, price=p)],
                )

            elif w == 0 and prev_w != 0:
                # Close position to flat
                if open_trade is not None:
                    open_trade = _close_trade(open_trade, d, p, close, common_dates)
                    trades.append(open_trade)
                    open_trade = None

            else:
                # Same direction, partial weight change (scaling in/out)
                if open_trade is not None:
                    open_trade.weight_history.append(
                        WeightEvent(date=d, weight=w, price=p)
                    )

        # Close any remaining open trade at last bar
        if open_trade is not None:
            last_date = _to_date(common_dates[-1])
            last_price = float(close.iloc[-1])
            open_trade = _close_trade(
                open_trade, last_date, last_price, close, common_dates
            )
            trades.append(open_trade)

    return trades


def _close_trade(
    trade: Trade,
    exit_date: date_type,
    exit_price: float,
    close: pd.Series,
    dates: pd.DatetimeIndex,
) -> Trade:
    """Fill in exit fields and compute return/MAE/MFE for a trade."""
    trade.exit_date = exit_date
    trade.exit_price = exit_price

    # Holding days (trading days)
    entry_loc = dates.get_loc(pd.Timestamp(trade.entry_date))
    exit_loc = dates.get_loc(pd.Timestamp(exit_date))
    trade.holding_days = int(exit_loc - entry_loc)

    # Compute return, MAE, MFE over the trade window
    trade_prices = close.iloc[entry_loc:exit_loc + 1]

    if len(trade_prices) > 0 and trade.entry_price > 0:
        price_returns = trade_prices / trade.entry_price - 1

        if trade.direction == "long":
            trade.return_pct = float(
                (exit_price / trade.entry_price - 1) * 100
            )
            trade.mae_pct = float(price_returns.min() * 100)
            trade.mfe_pct = float(price_returns.max() * 100)
        else:  # short
            trade.return_pct = float(
                (1 - exit_price / trade.entry_price) * 100
            )
            trade.mae_pct = float(-price_returns.max() * 100)
            trade.mfe_pct = float(-price_returns.min() * 100)

    return trade


def _to_date(dt) -> date_type:
    """Convert a pandas Timestamp or datetime to a date object."""
    if hasattr(dt, "date"):
        return dt.date() if callable(dt.date) else dt.date
    return dt
