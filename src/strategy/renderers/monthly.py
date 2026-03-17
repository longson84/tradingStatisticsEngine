"""Monthly returns tables and statistics renderers."""
from typing import Any, Dict

import pandas as pd
import streamlit as st

from src.constants import COLOR_NEGATIVE, COLOR_POSITIVE, fmt_pct, format_percentile_columns


_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_PERCENTILES = [95, 90, 80, 70, 60, 50, 40, 30, 20, 10, 5]


def build_monthly_returns_df(equity: pd.Series) -> pd.DataFrame:
    monthly = equity.resample("ME").last()
    monthly_ret = monthly.pct_change().dropna() * 100

    years = sorted(monthly_ret.index.year.unique(), reverse=True)
    rows = []
    for yr in years:
        year_monthly_vals = []
        month_vals: Dict[str, Any] = {}
        for m_i, m_name in enumerate(_MONTHS, start=1):
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


def style_monthly_table(df: pd.DataFrame) -> "pd.io.formats.style.Styler":
    def _cell_style(val):
        if not isinstance(val, str) or val == "":
            return ""
        try:
            numeric = float(val.replace(",", "").replace("%", ""))
        except ValueError:
            return ""
        if numeric > 0:
            return COLOR_POSITIVE
        elif numeric < 0:
            return COLOR_NEGATIVE
        return ""

    color_cols = [c for c in _MONTHS + ["Annual"] if c in df.columns]
    return df.style.applymap(_cell_style, subset=color_cols)


def build_monthly_stats_df(equity: pd.Series) -> pd.DataFrame:
    monthly = equity.resample("ME").last()
    monthly_ret = monthly.pct_change().dropna() * 100

    rows = []
    for m_i, m_name in enumerate(_MONTHS, start=1):
        vals = monthly_ret[monthly_ret.index.month == m_i].tolist()
        row: Dict[str, Any] = {"Month": m_name, **format_percentile_columns(vals, _PERCENTILES)}
        rows.append(row)
    return pd.DataFrame(rows)


def style_monthly_stats_df(df: pd.DataFrame) -> "pd.io.formats.style.Styler":
    color_cols = [f"P{p}" for p in _PERCENTILES if f"P{p}" in df.columns]

    def _cell_style(val):
        if not isinstance(val, str) or val == "—":
            return ""
        try:
            numeric = float(val.replace(",", "").replace("%", ""))
        except ValueError:
            return ""
        if numeric > 0:
            return COLOR_POSITIVE
        elif numeric < 0:
            return COLOR_NEGATIVE
        return ""

    return df.style.applymap(_cell_style, subset=color_cols)


def build_trade_entry_month_stats_df(trades, value_attr: str = "return_pct") -> pd.DataFrame:
    closed = [t for t in trades if t.status == "closed" and getattr(t, value_attr) is not None]

    rows = []
    for m_i, m_name in enumerate(_MONTHS, start=1):
        month_vals = [getattr(t, value_attr) for t in closed if t.entry_date.month == m_i]
        row: Dict[str, Any] = {
            "Month": m_name,
            "# Trades": len(month_vals),
            **format_percentile_columns(month_vals, _PERCENTILES),
        }
        rows.append(row)
    return pd.DataFrame(rows)


def render_monthly_returns_tables(
    strat_equity: pd.Series,
    bh_equity: pd.Series,
    ticker: str,
    trades: list = None,
) -> None:
    st.subheader("📅 Monthly Returns — Strategy Position")
    strat_df = build_monthly_returns_df(strat_equity)
    if strat_df.empty:
        st.info("Not enough data for monthly breakdown.")
    else:
        st.dataframe(style_monthly_table(strat_df), hide_index=True,
                     use_container_width=True, height=38 + len(strat_df) * 35)

    st.subheader("📅 Monthly Returns — Buy & Hold Position")
    bh_df = build_monthly_returns_df(bh_equity)
    if bh_df.empty:
        st.info("Not enough data for monthly breakdown.")
    else:
        st.dataframe(style_monthly_table(bh_df), hide_index=True,
                     use_container_width=True, height=38 + len(bh_df) * 35)

    st.divider()

    st.subheader("📊 Monthly Statistics — Strategy Position")
    strat_stats = build_monthly_stats_df(strat_equity)
    st.dataframe(style_monthly_stats_df(strat_stats), hide_index=True,
                 use_container_width=True, height=38 + 12 * 35)

    st.subheader("📊 Monthly Statistics — Buy & Hold Position")
    bh_stats = build_monthly_stats_df(bh_equity)
    st.dataframe(style_monthly_stats_df(bh_stats), hide_index=True,
                 use_container_width=True, height=38 + 12 * 35)

    if trades:
        st.divider()
        st.subheader("📊 Monthly Statistics — Return by Trade Entry Month")
        st.caption("Percentile distribution of trade returns grouped by the month the position was opened.")
        entry_stats = build_trade_entry_month_stats_df(trades, "return_pct")
        st.dataframe(style_monthly_stats_df(entry_stats), hide_index=True,
                     use_container_width=True, height=38 + 12 * 35)

        st.subheader("📊 Monthly Statistics — MFE by Trade Entry Month")
        st.caption("Percentile distribution of Maximum Favorable Excursion grouped by the month the position was opened.")
        mfe_stats = build_trade_entry_month_stats_df(trades, "mfe_pct")
        st.dataframe(style_monthly_stats_df(mfe_stats), hide_index=True,
                     use_container_width=True, height=38 + 12 * 35)
