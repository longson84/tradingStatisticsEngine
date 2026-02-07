import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from src.signals import SignalStrategy

class ChartVisualizer:
    @staticmethod
    def create_chart(ticker: str, df: pd.DataFrame, signal_series: pd.Series, strategy: SignalStrategy) -> go.Figure:
        """
        Tạo biểu đồ tương tác với Plotly.
        - Row 1: Giá (Tô màu theo độ hiếm)
        - Row 2: Signal (Có các đường reference line)
        """
        # Align data: Chỉ lấy dữ liệu giá tại những ngày có signal
        df_aligned = df.loc[signal_series.index]
        
        # 1. Get configuration
        config = strategy.visualization_config
        threshold_percents = config.get("thresholds", [0.01, 0.05, 0.10])
        colors = config.get("colors", ["green", "#ffd700", "red"]) # 1%, 5%, 10%
        
        # 2. Calculate actual threshold values from signal history
        # Percentiles are 0-100 in numpy
        threshold_values = [np.percentile(signal_series, p * 100) for p in threshold_percents]
        
        # 3. Create Subplots
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            row_heights=[0.6, 0.4],
            subplot_titles=(f"Price Action - {ticker}", f"Signal: {strategy.name}")
        )
        
        # --- CHART 1: PRICE (Row 1) ---
        # Base Line (Black/Grey) - All data
        fig.add_trace(
            go.Scatter(
                x=df_aligned.index, y=df_aligned['Close'],
                mode='lines',
                name='Price',
                line=dict(color='black', width=1),
                hovertemplate='Price: %{y:,.2f}<extra></extra>'
            ),
            row=1, col=1
        )
        
        # Overlay Colored Lines based on Rarity
        # Layering Order: Red (10%) -> Yellow (5%) -> Green (1%)
        # Map: 10% -> Red (Index 2), 5% -> Yellow (Index 1), 1% -> Green (Index 0)
        layer_indices = [2, 1, 0] 
        
        for i in layer_indices:
            if i >= len(threshold_values) or i >= len(colors):
                continue
                
            thresh_val = threshold_values[i]
            color = colors[i]
            label = f"Rarity Top {threshold_percents[i]*100:.0f}%"
            
            # Mask: Signal <= Threshold
            mask = signal_series <= thresh_val
            
            # Create a copy for plotting segments
            filtered_close = df_aligned['Close'].copy()
            filtered_close[~mask] = np.nan
            
            # Chỉ plot nếu có dữ liệu
            if not filtered_close.dropna().empty:
                fig.add_trace(
                    go.Scatter(
                        x=filtered_close.index, y=filtered_close,
                        mode='lines',
                        name=label,
                        line=dict(color=color, width=2),
                        connectgaps=False, 
                        hovertemplate=f'{label}: %{{y:,.2f}}<extra></extra>'
                    ),
                    row=1, col=1
                )

        # --- CHART 2: SIGNAL (Row 2) ---
        # Signal Line
        fig.add_trace(
            go.Scatter(
                x=signal_series.index, y=signal_series,
                mode='lines',
                name='Signal Value',
                line=dict(color='blue', width=1.5),
                hovertemplate='Signal: %{y:.4f}<extra></extra>'
            ),
            row=2, col=1
        )
        
        # Horizontal Threshold Lines
        for i, val in enumerate(threshold_values):
            if i >= len(colors): continue
            
            fig.add_hline(
                y=val, 
                line_dash="dot", 
                line_color=colors[i], 
                annotation_text=f"{threshold_percents[i]*100:.0f}%", 
                row=2, col=1
            )

        fig.update_layout(height=800, hovermode="x unified", showlegend=True)
        return fig

    @staticmethod
    def create_distribution_chart(signal_series: pd.Series, current_value: float, strategy_name: str) -> go.Figure:
        """
        Tạo biểu đồ phân phối (Histogram) của tín hiệu.
        Và đánh dấu vị trí hiện tại.
        """
        fig = go.Figure()

        # 1. Histogram
        fig.add_trace(go.Histogram(
            x=signal_series,
            name='Phân phối lịch sử',
            nbinsx=100,
            marker_color='lightblue',
            opacity=0.7
        ))

        # 2. Vertical Line for Current Value
        fig.add_vline(
            x=current_value,
            line_width=3,
            line_dash="dash",
            line_color="red",
            annotation_text="Hiện tại",
            annotation_position="top right"
        )

        fig.update_layout(
            title=f"Phân phối tín hiệu: {strategy_name}",
            xaxis_title="Giá trị Tín hiệu",
            yaxis_title="Số lần xuất hiện (Ngày)",
            height=400,
            showlegend=True,
            bargap=0.1
        )
        
        return fig
