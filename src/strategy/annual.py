"""Annual trade summary builder — pure DataFrame construction, no UI."""
from collections import defaultdict
from typing import Any, Dict

import numpy as np
import pandas as pd

from src.constants import ANNUAL_PERCENTILES
from src.fmt import fmt_pct, format_percentile_columns


def build_annual_summary_df(closed: list) -> pd.DataFrame:
    """Build per-year trade statistics DataFrame from closed trades.

    Returns a display-ready DataFrame (sorted recent-first, numeric helper column dropped).
    """
    year_trades: dict = defaultdict(list)
    for t in sorted(closed, key=lambda x: x.entry_date):
        year_trades[t.entry_date.year].append(t.return_pct)

    rows = []
    for yr in sorted(year_trades.keys(), reverse=True):
        rets = year_trades[yr]
        wins = [r for r in rets if r > 0]
        losses = [r for r in rets if r <= 0]

        capital = 1000.0
        for r in rets:
            capital *= (1 + r / 100)
        total_return_pct = (capital / 1000.0 - 1) * 100

        row: Dict[str, Any] = {
            "Year": str(yr),
            "Trades": len(rets),
            "Total Return (%)": fmt_pct(total_return_pct),
            "Win Rate": fmt_pct(len(wins) / len(rets) * 100),
            "Avg. Win (%)": fmt_pct(float(np.mean(wins))) if wins else "—",
            "Avg. Loss (%)": fmt_pct(float(np.mean(losses))) if losses else "—",
            **format_percentile_columns(rets, ANNUAL_PERCENTILES),
            "_total_return_num": total_return_pct,
        }
        rows.append(row)

    df = pd.DataFrame(rows)
    return df.drop(columns=["_total_return_num"])
