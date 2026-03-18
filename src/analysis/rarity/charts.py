"""Plotly chart builders for rarity analysis — no Streamlit."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.factors.base import BaseFactor
from src.shared.constants import PLOTLY_ACTIVE, PLOTLY_NEGATIVE, PLOTLY_POSITIVE, VISUALIZATION_THRESHOLDS

_CHART_COLORS = [PLOTLY_POSITIVE, PLOTLY_ACTIVE, PLOTLY_NEGATIVE]


def create_price_factor_chart(
    ticker: str,
    df: pd.DataFrame,
    factor_series: pd.Series,
    factor: BaseFactor,
) -> go.Figure:
    """Create price + factor dual-panel chart with rarity-coloured overlays."""
    df_aligned = df.loc[factor_series.index]

    threshold_percents = VISUALIZATION_THRESHOLDS
    colors = _CHART_COLORS

    threshold_values = [np.percentile(factor_series, p * 100) for p in threshold_percents]

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=[0.6, 0.4],
        subplot_titles=(f"Price Chart - {ticker}", f"Factor: {factor.name}")
    )

    fig.add_trace(
        go.Scatter(
            x=df_aligned.index, y=df_aligned['Close'],
            mode='lines',
            name='Price',
            line=dict(color='black', width=1),
            hovertemplate='Price: %{y:,.0f}<extra></extra>'
        ),
        row=1, col=1
    )

    layer_indices = [2, 1, 0]

    for i in layer_indices:
        if i >= len(threshold_values) or i >= len(colors):
            continue

        thresh_val = threshold_values[i]
        color = colors[i]
        label = f"Rarity Top {threshold_percents[i]*100:.0f}%"

        mask = factor_series <= thresh_val

        filtered_close = df_aligned['Close'].copy()
        filtered_close[~mask] = np.nan

        if not filtered_close.dropna().empty:
            fig.add_trace(
                go.Scatter(
                    x=filtered_close.index, y=filtered_close,
                    mode='lines',
                    name=label,
                    line=dict(color=color, width=2),
                    connectgaps=False,
                    hovertemplate=f'{label}: %{{y:,.0f}}<extra></extra>'
                ),
                row=1, col=1
            )

    fig.add_trace(
        go.Scatter(
            x=factor_series.index, y=factor_series,
            mode='lines',
            name='Factor Value',
            line=dict(color='blue', width=1.5),
            hovertemplate='Factor: %{y:.4f}<extra></extra>'
        ),
        row=2, col=1
    )

    for i, val in enumerate(threshold_values):
        if i >= len(colors):
            continue
        fig.add_hline(
            y=val,
            line_dash="dot",
            line_color=colors[i],
            annotation_text=f"{threshold_percents[i]*100:.0f}%",
            row=2, col=1
        )

    fig.update_layout(height=800, hovermode="x unified", showlegend=False)
    return fig


def create_factor_distribution_chart(
    factor_series: pd.Series,
    current_value: float,
    factor_name: str,
) -> go.Figure:
    """Create factor distribution histogram with current value marker."""
    fig = go.Figure()

    fig.add_trace(go.Histogram(
        x=factor_series,
        name='Phân phối lịch sử',
        nbinsx=100,
        marker_color='lightblue',
        opacity=0.7
    ))

    fig.add_vline(
        x=current_value,
        line_width=3,
        line_dash="dash",
        line_color="red",
        annotation_text="Hiện tại",
        annotation_position="top right"
    )

    fig.update_layout(
        xaxis_title="Giá trị Factor",
        yaxis_title="Số lần xuất hiện (Ngày)",
        height=400,
        showlegend=False,
        bargap=0.1
    )

    return fig
