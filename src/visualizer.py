import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

class UniversalVisualizer:
    @staticmethod
    def plot_dual_axis(price_series: pd.Series, signal_series: pd.Series, signal_name: str, thresholds: list = []):
        """
        Vẽ biểu đồ Price (Trục trái) và Signal (Trục phải).
        """
        # Align data
        common_idx = price_series.index.intersection(signal_series.index)
        prices = price_series.loc[common_idx]
        signals = signal_series.loc[common_idx]

        fig = make_subplots(specs=[[{"secondary_y": True}]])

        # 1. Vẽ Giá (Trục trái)
        fig.add_trace(
            go.Scatter(x=prices.index, y=prices, name="Price Asset", line=dict(color='#d4af37')),
            secondary_y=False,
        )

        # 2. Vẽ Signal (Trục phải)
        fig.add_trace(
            go.Scatter(x=signals.index, y=signals, name=signal_name, line=dict(color='#2c3e50', width=1.5), opacity=0.8),
            secondary_y=True,
        )

        # 3. Vẽ các đường Threshold
        colors = ['red', 'orange', 'yellow']
        for i, thresh in enumerate(thresholds):
            color = colors[i] if i < len(colors) else 'grey'
            fig.add_hline(y=thresh, line_dash="dash", line_color=color, secondary_y=True, annotation_text=f"Thresh: {thresh:.4f}")

        # Cấu hình Layout
        fig.update_layout(
            title_text=f"Capital OS Analytics: Price vs {signal_name}",
            template="plotly_white",
            hovermode="x unified",
            height=700
        )
        
        fig.update_yaxes(title_text="Price (Log)", type="log", secondary_y=False)
        fig.update_yaxes(title_text=signal_name, secondary_y=True, showgrid=False)

        fig.show()