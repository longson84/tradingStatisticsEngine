"""Signal generation utilities for strategies."""
from __future__ import annotations

from typing import Tuple

import numpy as np
import pandas as pd


def generate_trade_signals(
    price: pd.Series,
    crossover_series: pd.Series,
    buy_lag: int,
    sell_lag: int,
) -> Tuple[pd.Series, pd.Series]:
    """Detect zero-crossings in crossover_series and schedule buy/sell signals
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
            target_i = i + buy_lag
            if target_i < len(common_idx):
                if np.sign(cross.iloc[target_i]) >= 0:
                    buy_signals.iloc[target_i] = True

        elif prev_sign > 0 and cur_sign <= 0:
            target_i = i + sell_lag
            if target_i < len(common_idx):
                if np.sign(cross.iloc[target_i]) <= 0:
                    sell_signals.iloc[target_i] = True

        if cur_sign != 0:
            prev_sign = cur_sign

    return buy_signals, sell_signals
