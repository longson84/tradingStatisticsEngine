"""Monthly returns tables and statistics renderers."""
import pandas as pd
import streamlit as st

from src.strategy.monthly import (
    build_monthly_returns_df,
    build_monthly_stats_df,
    build_trade_entry_month_stats_df,
)
from src.styling import style_monthly_returns_table, style_monthly_stats_table


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
        st.dataframe(style_monthly_returns_table(strat_df), hide_index=True,
                     use_container_width=True, height=38 + len(strat_df) * 35)

    st.subheader("📅 Monthly Returns — Buy & Hold Position")
    bh_df = build_monthly_returns_df(bh_equity)
    if bh_df.empty:
        st.info("Not enough data for monthly breakdown.")
    else:
        st.dataframe(style_monthly_returns_table(bh_df), hide_index=True,
                     use_container_width=True, height=38 + len(bh_df) * 35)

    st.divider()

    st.subheader("📊 Monthly Statistics — Strategy Position")
    strat_stats = build_monthly_stats_df(strat_equity)
    st.dataframe(style_monthly_stats_table(strat_stats), hide_index=True,
                 use_container_width=True, height=38 + 12 * 35)

    st.subheader("📊 Monthly Statistics — Buy & Hold Position")
    bh_stats = build_monthly_stats_df(bh_equity)
    st.dataframe(style_monthly_stats_table(bh_stats), hide_index=True,
                 use_container_width=True, height=38 + 12 * 35)

    if trades:
        st.divider()
        st.subheader("📊 Monthly Statistics — Return by Trade Entry Month")
        st.caption("Percentile distribution of trade returns grouped by the month the position was opened.")
        entry_stats = build_trade_entry_month_stats_df(trades, "return_pct")
        st.dataframe(style_monthly_stats_table(entry_stats), hide_index=True,
                     use_container_width=True, height=38 + 12 * 35)

        st.subheader("📊 Monthly Statistics — MFE by Trade Entry Month")
        st.caption("Percentile distribution of Maximum Favorable Excursion grouped by the month the position was opened.")
        mfe_stats = build_trade_entry_month_stats_df(trades, "mfe_pct")
        st.dataframe(style_monthly_stats_table(mfe_stats), hide_index=True,
                     use_container_width=True, height=38 + 12 * 35)
