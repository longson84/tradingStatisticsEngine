"""Strategy health / deterioration section renderer."""
import pandas as pd
import streamlit as st

from src.constants import ANNUAL_PERCENTILES
from src.strategy.annual import build_annual_summary_df
from src.styling import style_pct_cell


# ---------------------------------------------------------------------------
# 1. Annual Trade Summary
# ---------------------------------------------------------------------------

def _render_annual_summary(closed: list, _ks: str) -> None:
    st.subheader("Annual Trade Summary")
    st.caption("Per-year trade statistics. Recent years at the top.")

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


# ---------------------------------------------------------------------------
# Public entry point — composes the 4 sections
# ---------------------------------------------------------------------------

def render_deterioration_section(trades, strat_equity: pd.Series, ticker: str, key_suffix: str = "") -> None:
    _ks = key_suffix or ticker
    closed = [
        t for t in trades
        if t.status == "closed" and t.return_pct is not None and t.entry_date is not None
    ]

    st.subheader("📉 Strategy Health Over Time")
    st.caption(
        "These views help identify whether strategy performance is deteriorating. "
        "Strong aggregate stats can mask recent weakness — check the most recent years and rolling windows."
    )

    _render_annual_summary(closed, _ks)
