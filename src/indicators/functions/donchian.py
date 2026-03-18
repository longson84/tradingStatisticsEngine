"""Donchian Channel computation."""
from __future__ import annotations

from typing import Tuple

import pandas as pd


def donchian_channels(
    high: pd.Series,
    low: pd.Series,
    entry_length: int,
    exit_length: int,
) -> Tuple[pd.Series, pd.Series]:
    """Compute Donchian Channels.

    Args:
        high: High price series.
        low: Low price series.
        entry_length: Look-back for upper channel (entry breakout).
        exit_length: Look-back for lower channel (exit breakout).

    Returns:
        (upper_channel, lower_channel) — both shifted by 1 bar (previous day's extremes).
    """
    upper = high.rolling(entry_length).max().shift(1)
    lower = low.rolling(exit_length).min().shift(1)
    return upper, lower
