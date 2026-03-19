"""Shared Streamlit UI utilities."""
from datetime import date
from typing import Optional

import streamlit as st
import plotly.graph_objects as go

from src.shared.constants import YFINANCE_PRESETS


def plot_chart(fig: go.Figure) -> None:
    """Render a Plotly figure, compatible with both old and new Streamlit versions."""
    try:
        st.plotly_chart(fig, width="stretch")
    except TypeError:
        st.plotly_chart(fig, use_container_width=True)


def sidebar_data_source(key_prefix: str) -> str:
    """Data source selectbox (yfinance / vnstock)."""
    return st.sidebar.selectbox(
        "Data Source:",
        ["yfinance", "vnstock"],
        key=f"{key_prefix}_data_source",
        help="yfinance: global tickers (BTC-USD, AAPL…) | vnstock: Vietnamese stocks (VCB, VIC…)",
    )


def sidebar_ticker_input(
    data_source: str,
    key_prefix: str,
    *,
    multi: bool = True,
) -> list[str] | str:
    """Ticker input widget with optional symbol group selection."""
    if multi:
        VNSTOCK_GROUPS = ["— type manually —", "VN30", "VN100", "VNMidCap"]
        YFINANCE_GROUPS = ["— type manually —"] + list(YFINANCE_PRESETS.keys())
        groups = VNSTOCK_GROUPS if data_source == "vnstock" else YFINANCE_GROUPS

        group_key = f"{key_prefix}_symbol_group"
        prev_ds_key = f"{key_prefix}_symbol_group_ds"
        if st.session_state.get(prev_ds_key) != data_source:
            st.session_state[group_key] = 0
            st.session_state[prev_ds_key] = data_source

        group_choice = st.sidebar.selectbox(
            "Symbol Group:",
            groups,
            key=group_key,
        )

        if data_source == "vnstock" and group_choice != "— type manually —":
            from src.app.data_loader import load_vnstock_group
            tickers = load_vnstock_group(group_choice)
            st.sidebar.caption(f"{len(tickers)} symbols from {group_choice}")
            return tickers
        elif data_source == "yfinance" and group_choice != "— type manually —":
            tickers = YFINANCE_PRESETS[group_choice]
            st.sidebar.caption(f"{len(tickers)} symbols from {group_choice}")
            return tickers

    default_ticker = "BTC-USD" if data_source == "yfinance" else "VCB"
    label = "Ticker:" if not multi else "Tickers (space-separated):"
    ticker_input = st.sidebar.text_input(
        label,
        value=default_ticker,
        key=f"{key_prefix}_ticker_input",
    )

    if multi:
        return [t.strip().upper() for t in ticker_input.split() if t.strip()]
    return ticker_input.strip().upper()


def sidebar_from_date(key_prefix: str) -> Optional[date]:
    """Backtest from-date picker."""
    st.sidebar.divider()
    return st.sidebar.date_input(
        "Backtest From Date:",
        value=None,
        help="Leave empty to use all available data. Set a later date to avoid early-data bias (tiny prices → inflated % returns).",
        key=f"{key_prefix}_from_date",
    )
