"""Chart builders for the Parameter Sweep page.

All functions are pure — they accept plain data and return a go.Figure.
No Streamlit calls; rendering is handled by the caller via plot_chart().
"""
from typing import List, Tuple

import numpy as np
import plotly.graph_objects as go

from src.constants import PLOTLY_NEGATIVE, PLOTLY_POSITIVE


def _to_log(v):
    """Convert a percentage return to log return, preserving None."""
    return np.log1p(v / 100) * 100 if v is not None else None


def build_return_chart(
    lengths_str: List[str],
    total_returns: List[float],
    bh_return_val: float,
) -> go.Figure:
    """Bar chart: total strategy return vs buy-and-hold baseline."""
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=lengths_str, y=total_returns,
        name="Total Return %",
        marker_color="#FFD700",
        hovertemplate="%{x}: %{y:.2f}%<extra>Total Return</extra>",
    ))
    fig.add_hline(
        y=bh_return_val, line_dash="dash", line_color="gray", line_width=2,
        annotation_text=f"B&H: {bh_return_val:.1f}%",
        annotation_position="top left",
    )
    fig.update_layout(
        title="Total Return % by MA Length",
        xaxis_title="MA Length", yaxis_title="Return %",
        height=380, hovermode="x unified", showlegend=False,
    )
    return fig


def build_drawdown_chart(
    lengths_str: List[str],
    max_dds: List[float],
) -> go.Figure:
    """Bar chart: max drawdown per MA length."""
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=lengths_str, y=max_dds,
        name="Max Drawdown %",
        marker_color="#FF6B6B",
        hovertemplate="%{x}: %{y:.2f}%<extra>Max DD</extra>",
    ))
    fig.update_layout(
        title="Max Drawdown % by MA Length",
        xaxis_title="MA Length", yaxis_title="Drawdown %",
        height=380, hovermode="x unified", showlegend=False,
    )
    return fig


def build_trade_count_chart(
    lengths_str: List[str],
    win_counts: List[int],
    loss_counts: List[int],
) -> go.Figure:
    """Diverging bar chart: wins up, losses down, total labelled above."""
    total_counts = [w + l for w, l in zip(win_counts, loss_counts)]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=lengths_str, y=win_counts,
        name="Win Trades",
        marker_color=PLOTLY_POSITIVE,
        hovertemplate="%{x}: %{y} wins<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=lengths_str, y=[-l for l in loss_counts],
        name="Loss Trades",
        marker_color=PLOTLY_NEGATIVE,
        hovertemplate="%{x}: %{customdata} losses<extra></extra>",
        customdata=loss_counts,
    ))
    for x_val, w, total in zip(lengths_str, win_counts, total_counts):
        fig.add_annotation(
            x=x_val, y=w,
            text=str(total),
            showarrow=False, yshift=10,
            font=dict(size=11, color="white"),
        )
    fig.update_layout(
        title="Trade Count by MA Length",
        xaxis_title="MA Length", yaxis_title="# Trades",
        barmode="relative",
        height=380, hovermode="x unified",
    )
    return fig


def build_win_rate_chart(
    lengths_str: List[str],
    win_rates: List[float],
) -> go.Figure:
    """Bar chart: win rate per MA length, green ≥ 50% / red < 50%."""
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=lengths_str, y=win_rates,
        marker_color=[PLOTLY_POSITIVE if w >= 50 else PLOTLY_NEGATIVE for w in win_rates],
        hovertemplate="%{x}: %{y:.1f}%<extra>Win Rate</extra>",
    ))
    fig.add_hline(y=50, line_dash="dash", line_color="gray", line_width=1,
                  annotation_text="50%", annotation_position="top left")
    fig.update_layout(
        title="Win Rate % by MA Length",
        xaxis_title="MA Length", yaxis_title="Win Rate %",
        height=380, hovermode="x unified", showlegend=False,
    )
    return fig


def build_boxplot_chart(
    sweep_results: List[Tuple],
    closed_returns_by_len: List[List[float]],
    use_log: bool,
) -> go.Figure:
    """Box plot: P10–P90 whiskers, P30–P70 body, one box per MA length."""
    fig = go.Figure()
    for i, (length, _label, _core) in enumerate(sweep_results):
        cr = closed_returns_by_len[i]
        if not cr:
            continue

        p10, p30, p50, p70, p90 = (float(np.percentile(cr, p)) for p in (10, 30, 50, 70, 90))
        if use_log:
            p10, p30, p50, p70, p90 = (_to_log(v) for v in (p10, p30, p50, p70, p90))

        fig.add_trace(go.Box(
            x=[str(length)],
            lowerfence=[p10], q1=[p30], median=[p50], q3=[p70], upperfence=[p90],
            name=str(length),
            marker_color="#4ECDC4",
            fillcolor="rgba(78, 205, 196, 0.3)",
            line=dict(color="#4ECDC4"),
            whiskerwidth=0.5,
            showlegend=False,
            hoverinfo="y",
        ))

    fig.add_hline(y=0, line_color="gray", line_width=1)
    fig.update_layout(
        title="Trade Return Distribution by MA Length (P30–P70 box, P10–P90 whiskers)",
        xaxis_title="MA Length",
        yaxis_title="Log Return %" if use_log else "Return %",
        height=480, hovermode="x unified", showlegend=True,
    )
    return fig
