"""Return distribution and non-negative distribution renderers."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.constants import build_percentile_breakdown, fmt_pct
from src.ui import plot_chart


def render_return_distribution(trades) -> None:
    closed = [t for t in trades if t.status == "closed" and t.return_pct is not None]
    if len(closed) < 2:
        st.info("Not enough closed trades to show distribution.")
        return

    returns = [t.return_pct for t in closed]
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r <= 0]

    rows = build_percentile_breakdown(returns, "Return %")

    col_stats, col_buckets = st.columns(2)

    with col_stats:
        st.markdown("**Percentile breakdown**")
        st.dataframe(
            pd.DataFrame(rows),
            hide_index=True,
            use_container_width=True,
            height=38 + len(rows) * 35,
        )

    buckets = [
        ("< -20%",      float("-inf"), -20),
        ("-20 → -10%",         -20,   -10),
        ("-10 → -5%",          -10,    -5),
        ("-5 → 0%",             -5,     0),
        ("0 → 5%",               0,     5),
        ("5 → 10%",              5,    10),
        ("10 → 20%",            10,    20),
        ("> 20%",               20, float("inf")),
    ]
    total = len(returns)
    bucket_rows = []
    for label, lo, hi in buckets:
        subset = [r for r in returns if lo < r <= hi] if hi != float("inf") else [r for r in returns if r > lo]
        count = len(subset)
        bucket_rows.append({
            "Range": label,
            "Count": count,
            "% of Total": fmt_pct(count / total * 100) if total else "0.00%",
            "Avg Return": fmt_pct(np.mean(subset)) if subset else "—",
        })

    with col_buckets:
        st.markdown("**Return buckets**")
        st.dataframe(
            pd.DataFrame(bucket_rows),
            hide_index=True,
            use_container_width=True,
            height=38 + len(bucket_rows) * 35,
        )

    fig = go.Figure()
    if wins:
        fig.add_trace(go.Histogram(x=wins, name="Win",
                                   marker_color="rgba(34, 197, 94, 0.7)", xbins=dict(size=2)))
    if losses:
        fig.add_trace(go.Histogram(x=losses, name="Loss",
                                   marker_color="rgba(239, 68, 68, 0.7)", xbins=dict(size=2)))

    mean_r = float(np.mean(returns))
    median_r = float(np.median(returns))
    fig.add_vline(x=mean_r, line_dash="dash", line_color="white",
                  annotation_text=f"Mean {mean_r:.1f}%", annotation_position="top right")
    fig.add_vline(x=median_r, line_dash="dot", line_color="yellow",
                  annotation_text=f"Median {median_r:.1f}%", annotation_position="top left")
    fig.add_vline(x=0, line_color="gray", line_width=1)
    fig.update_layout(barmode="overlay", height=350, xaxis_title="Return %",
                      yaxis_title="# Trades", hovermode="x unified",
                      showlegend=True, margin=dict(t=30))
    plot_chart(fig)


def render_nonneg_distribution(values: list, metric_label: str, bar_color: str) -> None:
    if len(values) < 2:
        st.info("Not enough closed trades to show distribution.")
        return

    pct_rows = build_percentile_breakdown(values, metric_label)

    buckets = [
        ("0 → 5%",      0,   5),
        ("5 → 10%",     5,  10),
        ("10 → 20%",   10,  20),
        ("20 → 30%",   20,  30),
        ("30 → 50%",   30,  50),
        ("50 → 100%",  50, 100),
        ("> 100%",    100, float("inf")),
    ]
    total = len(values)
    bucket_rows = []
    for label, lo, hi in buckets:
        subset = [v for v in values if lo < v <= hi] if hi != float("inf") else [v for v in values if v > lo]
        count = len(subset)
        bucket_rows.append({
            "Range": label,
            "Count": count,
            "% of Total": fmt_pct(count / total * 100) if total else "0.00%",
            f"Avg {metric_label}": fmt_pct(np.mean(subset)) if subset else "—",
        })

    col_stats, col_buckets = st.columns(2)
    with col_stats:
        st.markdown("**Percentile breakdown**")
        st.dataframe(pd.DataFrame(pct_rows), hide_index=True, use_container_width=True,
                     height=38 + len(pct_rows) * 35)
    with col_buckets:
        st.markdown("**Buckets**")
        st.dataframe(pd.DataFrame(bucket_rows), hide_index=True, use_container_width=True,
                     height=38 + len(bucket_rows) * 35)

    mean_v = float(np.mean(values))
    median_v = float(np.median(values))
    fig = go.Figure()
    fig.add_trace(go.Histogram(x=values, name=metric_label, marker_color=bar_color, xbins=dict(size=2)))
    fig.add_vline(x=mean_v, line_dash="dash", line_color="white",
                  annotation_text=f"Mean {mean_v:.1f}%", annotation_position="top right")
    fig.add_vline(x=median_v, line_dash="dot", line_color="yellow",
                  annotation_text=f"Median {median_v:.1f}%", annotation_position="top left")
    fig.update_layout(height=350, xaxis_title=f"{metric_label} (%)", yaxis_title="# Trades",
                      hovermode="x unified", showlegend=False, margin=dict(t=30))
    plot_chart(fig)
