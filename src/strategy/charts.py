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
