"""Strategy health / deterioration section renderer."""
from collections import defaultdict
from typing import Any, Dict

import numpy as np
import pandas as pd
import streamlit as st

from src.fmt import fmt_pct, format_percentile_columns
from src.styling import style_positive_negative
from src.constants import ANNUAL_PERCENTILES


# ---------------------------------------------------------------------------
# 1. Annual Trade Summary
# ---------------------------------------------------------------------------



def _render_annual_summary(closed: list, _ks: str) -> None:
    st.subheader("Annual Trade Summary")
    st.caption("Per-year trade statistics. Recent years at the top.")

    if len(closed) < 2:
        st.info("Not enough closed trades for annual breakdown.")
        return

    year_trades: dict = defaultdict(list)
    for t in sorted(closed, key=lambda x: x.entry_date):
        year_trades[t.entry_date.year].append(t.return_pct)

    annual_rows = []
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
        annual_rows.append(row)

    ann_df = pd.DataFrame(annual_rows)
    display_df = ann_df.drop(columns=["_total_return_num"])

    pct_cols = (
        ["Total Return (%)", "Avg. Win (%)", "Avg. Loss (%)"]
        + [f"P{p}" for p in _ANNUAL_PERCENTILES]
    )

    def _annual_cell_style(val):
        if not isinstance(val, str) or val == "":
            return ""
        try:
            numeric = float(val.replace(",", "").replace("%", ""))
        except ValueError:
            return ""
        return style_positive_negative(numeric, threshold=0)

    styled_ann = display_df.style.applymap(_annual_cell_style, subset=pct_cols)
    st.dataframe(styled_ann, hide_index=True, use_container_width=True,
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
