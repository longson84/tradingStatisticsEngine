"""Trade dataclass."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

import pandas as pd


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
    equity_at_close: Optional[float] = None  # strategy capital after this trade closes
