"""Plotly figure builders for strategy backtest — no Streamlit calls."""
import pandas as pd
import plotly.graph_objects as go

from src.constants import INITIAL_CAPITAL


def build_equity_chart(
    ticker: str,
    strat_equity: pd.Series,
    bh_equity: pd.Series,
    strategy_name: str,
    log_scale: bool = False,
) -> go.Figure:
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=bh_equity.index, y=bh_equity,
        mode="lines", name="Buy & Hold",
        line=dict(color="#90CAF9", width=1.5),
        hovertemplate="B&H: $%{y:,.0f}<extra></extra>",
    ))

    fig.add_trace(go.Scatter(
        x=strat_equity.index, y=strat_equity,
        mode="lines", name=strategy_name,
        line=dict(color="#FFD700", width=2),
        hovertemplate="Strategy: $%{y:,.0f}<extra></extra>",
    ))

    fig.add_hline(y=1000, line_dash="dot", line_color="gray", line_width=1)

    fig.update_layout(
        title=f"Equity Curve — {ticker} (Initial: ${INITIAL_CAPITAL:,.0f})",
        yaxis_title="Position Value (USD)",
        yaxis_type="log" if log_scale else "linear",
        height=500,
        hovermode="x unified",
        showlegend=True,
    )
    return fig


# Qualitative colour palette for sweep overlay lines
_SWEEP_COLORS = [
    "#FFD700", "#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4",
    "#FFEAA7", "#DDA0DD", "#98D8C8", "#F7DC6F", "#BB8FCE",
    "#85C1E9", "#F0B27A", "#82E0AA", "#F1948A", "#AED6F1",
    "#D7BDE2", "#A3E4D7", "#FAD7A0", "#A9CCE3", "#D5F5E3",
]


def build_sweep_equity_chart(
    ticker: str,
    sweep_results: list,
    bh_equity: pd.Series,
    log_scale: bool = False,
) -> go.Figure:
    """Build an overlay equity chart with one line per sweep variant + B&H baseline.

    Args:
        ticker: Ticker symbol for the chart title.
        sweep_results: List of (length, label, core_result_dict) tuples.
        bh_equity: Buy & Hold equity curve (same for all variants).
        log_scale: Whether to use log scale on Y axis.
    """
    fig = go.Figure()

    # B&H as dashed gray reference
    fig.add_trace(go.Scatter(
        x=bh_equity.index, y=bh_equity,
        mode="lines", name="Buy & Hold",
        line=dict(color="gray", width=1.5, dash="dash"),
        hovertemplate="B&H: $%{y:,.0f}<extra></extra>",
    ))

    for i, (length, label, core) in enumerate(sweep_results):
        color = _SWEEP_COLORS[i % len(_SWEEP_COLORS)]
        strat_eq = core["strat_equity"]
        fig.add_trace(go.Scatter(
            x=strat_eq.index, y=strat_eq,
            mode="lines", name=label,
            line=dict(color=color, width=1.5),
            hovertemplate=f"{label}: $%{{y:,.0f}}<extra></extra>",
        ))

    fig.add_hline(y=INITIAL_CAPITAL, line_dash="dot", line_color="gray", line_width=1)

    fig.update_layout(
        title=f"Parameter Sweep Equity — {ticker} (Initial: ${INITIAL_CAPITAL:,.0f})",
        yaxis_title="Position Value (USD)",
        yaxis_type="log" if log_scale else "linear",
        height=550,
        hovermode="x unified",
        showlegend=True,
    )
    return fig
