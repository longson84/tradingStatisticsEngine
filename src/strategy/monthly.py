"""Monthly data builders — pure DataFrame construction, no UI."""
from typing import Any, Dict

import pandas as pd

from src.constants import ANNUAL_PERCENTILES, MONTHS
from src.fmt import fmt_pct, format_percentile_columns


def build_monthly_returns_df(equity: pd.Series) -> pd.DataFrame:
    monthly = equity.resample("ME").last()
    monthly_ret = monthly.pct_change().dropna() * 100

    years = sorted(monthly_ret.index.year.unique(), reverse=True)
    rows = []
    for yr in years:
        year_monthly_vals = []
        month_vals: Dict[str, Any] = {}
        for m_i, m_name in enumerate(MONTHS, start=1):
            mask = (monthly_ret.index.year == yr) & (monthly_ret.index.month == m_i)
            vals = monthly_ret[mask]
            if len(vals) > 0:
                v = float(vals.iloc[0])
                month_vals[m_name] = fmt_pct(v)
                year_monthly_vals.append(v)
            else:
                month_vals[m_name] = ""

        if year_monthly_vals:
            compound = 1.0
            for v in year_monthly_vals:
                compound *= (1 + v / 100)
            annual = fmt_pct((compound - 1) * 100)
        else:
            annual = ""

        rows.append({"Year": str(yr), "Annual": annual, **month_vals})

    return pd.DataFrame(rows)


def build_monthly_stats_df(equity: pd.Series) -> pd.DataFrame:
    monthly = equity.resample("ME").last()
    monthly_ret = monthly.pct_change().dropna() * 100

    rows = []
    for m_i, m_name in enumerate(MONTHS, start=1):
        vals = monthly_ret[monthly_ret.index.month == m_i].tolist()
        row: Dict[str, Any] = {"Month": m_name, **format_percentile_columns(vals, ANNUAL_PERCENTILES)}
        rows.append(row)
    return pd.DataFrame(rows)


def build_trade_entry_month_stats_df(trades, value_attr: str = "return_pct") -> pd.DataFrame:
    closed = [t for t in trades if t.status == "closed" and getattr(t, value_attr) is not None]

    rows = []
    for m_i, m_name in enumerate(MONTHS, start=1):
        month_vals = [getattr(t, value_attr) for t in closed if t.entry_date.month == m_i]
        row: Dict[str, Any] = {
            "Month": m_name,
            "# Trades": len(month_vals),
            **format_percentile_columns(month_vals, ANNUAL_PERCENTILES),
        }
        rows.append(row)
    return pd.DataFrame(rows)
