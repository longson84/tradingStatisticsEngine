"""Return distribution and non-negative distribution renderers."""
from typing import Sequence

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.constants import PLOTLY_NEGATIVE, PLOTLY_POSITIVE
from src.strategy.utils import build_bucket_breakdown, build_percentile_breakdown
from src.ui import plot_chart


# ---------------------------------------------------------------------------
# Reusable table renderers
# ---------------------------------------------------------------------------

def _render_dataframe_table(rows: list[dict], title: str) -> None:
    """Helper to render a dataframe table with consistent styling."""
    st.markdown(f"**{title}**")
    st.dataframe(
        pd.DataFrame(rows),
        hide_index=True,
        use_container_width=True,
        height=38 + len(rows) * 35,
    )


# ---------------------------------------------------------------------------
# Private renderers
# ---------------------------------------------------------------------------


def _render_percentile_breakdown(values: list[float], metric_label: str) -> None:
    """Render a percentile breakdown table (P5–P95, Mean, Std Dev)."""
    pct_rows = build_percentile_breakdown(values, metric_label)
    _render_dataframe_table(pct_rows, "Percentile breakdown")


def _render_bucket_breakdown(
    values: list[float],
    metric_label: str,
    buckets: Sequence[tuple[str, float, float]],
    header: str = "Buckets",
) -> None:
    """Render a bucket count table (Range, Count, % of Total, Avg)."""
    bucket_rows = build_bucket_breakdown(values, metric_label, buckets)
    _render_dataframe_table(bucket_rows, header)


# ---------------------------------------------------------------------------
# Public renderers
# ---------------------------------------------------------------------------


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


