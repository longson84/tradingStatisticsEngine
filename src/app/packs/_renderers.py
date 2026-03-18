"""Streamlit rendering helpers shared across packs."""
from typing import Sequence

import pandas as pd
import streamlit as st

from src.shared.constants import ANNUAL_PERCENTILES
from src.shared.fmt import fmt_pct
from src.backtest.utils import build_bucket_breakdown, build_percentile_breakdown
from src.backtest.monthly import (
    build_monthly_returns_df,
    build_monthly_stats_df,
    build_trade_entry_month_stats_df,
)
from src.backtest.annual import build_annual_summary_df
from src.app.ui import plot_chart
from src.app.styling import style_monthly_returns_table, style_monthly_stats_table, style_pct_cell


# ---------------------------------------------------------------------------
# Performance summary
# ---------------------------------------------------------------------------

def render_performance_summary(perf, max_drawdown: float = 0.0) -> None:
    """Render strategy performance metrics (win rate, returns, trade counts, etc.)."""
    st.subheader("Performance Summary")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total Return", fmt_pct(perf.total_return))
    m2.metric("Win Rate", fmt_pct(perf.win_rate))
    m3.metric("Avg Win", fmt_pct(perf.avg_winning_return) if perf.avg_winning_return else "—")
    m4.metric("Avg Loss", fmt_pct(perf.avg_losing_return) if perf.avg_losing_return else "—")
    m5.metric("Max. DD", fmt_pct(max_drawdown))

    m6, m7, m8, m9, m10, m11 = st.columns(6)
    m6.metric("Closed Trades", str(perf.closed_trades))
    m7.metric("Win Trades", str(perf.win_count))
    m8.metric("Loss Trades", str(perf.loss_count))
    m9.metric("Max Consec. Loss", str(perf.max_consecutive_losses))
    m10.metric("Best Trade", fmt_pct(perf.best_trade_return))
    m11.metric("Worst Trade", fmt_pct(perf.worst_trade_return))


# ---------------------------------------------------------------------------
# Distribution tables
# ---------------------------------------------------------------------------

def _render_dataframe_table(rows: list[dict], title: str) -> None:
    st.markdown(f"**{title}**")
    st.dataframe(
        pd.DataFrame(rows),
        hide_index=True,
        use_container_width=True,
        height=38 + len(rows) * 35,
    )


def _render_percentile_breakdown(values: list[float], metric_label: str) -> None:
    pct_rows = build_percentile_breakdown(values, metric_label)
    _render_dataframe_table(pct_rows, "Percentile breakdown")


def _render_bucket_breakdown(
    values: list[float],
    metric_label: str,
    buckets: Sequence[tuple[str, float, float]],
    header: str = "Buckets",
) -> None:
    bucket_rows = build_bucket_breakdown(values, metric_label, buckets)
    _render_dataframe_table(bucket_rows, header)


def render_distribution(
    values: list[float],
    metric_label: str,
    buckets: Sequence[tuple[str, float, float]],
    bucket_header: str = "Buckets",
    yaxis_title: str = "# Trades",
) -> None:
    """Render distribution tables + histogram."""
    if len(values) < 2:
        st.info("Not enough closed trades to show distribution.")
        return

    col_stats, col_buckets = st.columns(2)
    with col_stats:
        _render_percentile_breakdown(values, metric_label)
    with col_buckets:
        _render_bucket_breakdown(values, metric_label, buckets, header=bucket_header)


# ---------------------------------------------------------------------------
# Monthly returns
# ---------------------------------------------------------------------------

def render_monthly_returns_tables(
    strat_equity: pd.Series,
    bh_equity: pd.Series,
    ticker: str,
    trades: list = None,
) -> None:
    st.subheader("Monthly Returns — Strategy Position")
    strat_df = build_monthly_returns_df(strat_equity)
    if strat_df.empty:
        st.info("Not enough data for monthly breakdown.")
    else:
        st.dataframe(style_monthly_returns_table(strat_df), hide_index=True,
                     use_container_width=True, height=38 + len(strat_df) * 35)

    st.subheader("Monthly Returns — Buy & Hold Position")
    bh_df = build_monthly_returns_df(bh_equity)
    if bh_df.empty:
        st.info("Not enough data for monthly breakdown.")
    else:
        st.dataframe(style_monthly_returns_table(bh_df), hide_index=True,
                     use_container_width=True, height=38 + len(bh_df) * 35)

    st.divider()

    st.subheader("Monthly Statistics — Strategy Position")
    strat_stats = build_monthly_stats_df(strat_equity)
    st.dataframe(style_monthly_stats_table(strat_stats), hide_index=True,
                 use_container_width=True, height=38 + 12 * 35)

    st.subheader("Monthly Statistics — Buy & Hold Position")
    bh_stats = build_monthly_stats_df(bh_equity)
    st.dataframe(style_monthly_stats_table(bh_stats), hide_index=True,
                 use_container_width=True, height=38 + 12 * 35)

    if trades:
        st.divider()
        st.subheader("Monthly Statistics — Return by Trade Entry Month")
        entry_stats = build_trade_entry_month_stats_df(trades, "return_pct")
        st.dataframe(style_monthly_stats_table(entry_stats), hide_index=True,
                     use_container_width=True, height=38 + 12 * 35)

        st.subheader("Monthly Statistics — MFE by Trade Entry Month")
        mfe_stats = build_trade_entry_month_stats_df(trades, "mfe_pct")
        st.dataframe(style_monthly_stats_table(mfe_stats), hide_index=True,
                     use_container_width=True, height=38 + 12 * 35)


# ---------------------------------------------------------------------------
# Deterioration / Strategy Health
# ---------------------------------------------------------------------------

def render_strategy_health_section(trades, strat_equity: pd.Series, ticker: str, key_suffix: str = "") -> None:
    closed = [
        t for t in trades
        if t.status == "closed" and t.return_pct is not None and t.entry_date is not None
    ]

    st.subheader("📉 Strategy Health Over Time")

    if len(closed) < 2:
        st.info("Not enough closed trades for annual breakdown.")
        return

    display_df = build_annual_summary_df(closed)
    pct_cols = (
        ["Total Return (%)", "Avg. Win (%)", "Avg. Loss (%)"]
        + [f"P{p}" for p in ANNUAL_PERCENTILES]
    )
    styled = display_df.style.applymap(style_pct_cell, subset=pct_cols)
    st.dataframe(styled, hide_index=True, use_container_width=True,
                 height=38 + len(display_df) * 35)
