from typing import Any, Dict

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from src.base import AnalysisPack, AnalysisResult
from src.strategy.strategies import BaseStrategy, MACrossoverStrategy, PriceVsMAStrategy
from src.strategy.analytics import (
    build_trades,
    calculate_drawdown_during_trades,
    calculate_trade_performance,
    get_current_position,
)


class StrategyBacktestPack(AnalysisPack):
    @property
    def pack_name(self) -> str:
        return "Strategy Backtest"

    def render_sidebar(self) -> Dict[str, Any]:
        st.sidebar.header("Strategy Backtest")

        ticker_input = st.sidebar.text_input(
            "Tickers (space-separated):",
            value="BTC-USD",
            key="strat_ticker_input",
        )
        tickers = [t.strip().upper() for t in ticker_input.split() if t.strip()]

        strategy_type = st.sidebar.selectbox(
            "Strategy Type:",
            ["Price vs MA", "MA Crossover"],
            key="strat_type",
        )

        if strategy_type == "Price vs MA":
            col1, col2 = st.sidebar.columns(2)
            ma_type = col1.selectbox("MA Type:", ["SMA", "EMA", "WMA"], key="pma_type")
            ma_len = col2.number_input("MA Length:", min_value=2, value=200, step=1, key="pma_len")
            col3, col4 = st.sidebar.columns(2)
            buy_lag = col3.number_input("Buy Lag (days):", min_value=0, value=1, step=1, key="pma_buy_lag")
            sell_lag = col4.number_input("Sell Lag (days):", min_value=0, value=1, step=1, key="pma_sell_lag")
            strategy = PriceVsMAStrategy(ma_type, int(ma_len), int(buy_lag), int(sell_lag))

        else:  # MA Crossover
            col1, col2 = st.sidebar.columns(2)
            fast_type = col1.selectbox("Fast MA Type:", ["EMA", "SMA", "WMA"], key="mac_fast_type")
            fast_len = col2.number_input("Fast Length:", min_value=2, value=50, step=1, key="mac_fast_len")
            col3, col4 = st.sidebar.columns(2)
            slow_type = col3.selectbox("Slow MA Type:", ["SMA", "EMA", "WMA"], key="mac_slow_type")
            slow_len = col4.number_input("Slow Length:", min_value=2, value=200, step=1, key="mac_slow_len")
            col5, col6 = st.sidebar.columns(2)
            buy_lag = col5.number_input("Buy Lag:", min_value=0, value=1, step=1, key="mac_buy_lag")
            sell_lag = col6.number_input("Sell Lag:", min_value=0, value=1, step=1, key="mac_sell_lag")
            strategy = MACrossoverStrategy(
                fast_type, int(fast_len), slow_type, int(slow_len), int(buy_lag), int(sell_lag)
            )

        return {"tickers": tickers, "strategy": strategy}

    def run_computation(self, ticker: str, df: pd.DataFrame, config: Dict) -> AnalysisResult:
        strategy: BaseStrategy = config["strategy"]

        try:
            crossover_series, buy_signals, sell_signals = strategy.compute(df)
            price = df["Close"]

            trades = build_trades(price, buy_signals, sell_signals)
            trades = calculate_drawdown_during_trades(trades, price)
            performance = calculate_trade_performance(trades)
            current_pos = get_current_position(price, crossover_series, buy_signals, sell_signals)
            ma_overlays = strategy.get_ma_overlays(df)

            fig = self._build_figure(ticker, price, crossover_series, buy_signals, sell_signals, ma_overlays, strategy)

            return AnalysisResult(
                ticker=ticker,
                pack_name=self.pack_name,
                price_series=price,
                signal_series=crossover_series,
                data={
                    "trades": trades,
                    "performance": performance,
                    "current_position": current_pos,
                    "fig": fig,
                    "signal_label": strategy.name,
                    "ma_overlays": ma_overlays,
                },
            )
        except Exception as e:
            return AnalysisResult(
                ticker=ticker,
                pack_name=self.pack_name,
                price_series=df["Close"] if "Close" in df.columns else pd.Series(dtype=float),
                signal_series=pd.Series(dtype=float),
                error=str(e),
            )

    def _build_figure(
        self,
        ticker: str,
        price: pd.Series,
        crossover_series: pd.Series,
        buy_signals: pd.Series,
        sell_signals: pd.Series,
        ma_overlays: Dict[str, pd.Series],
        strategy: BaseStrategy,
    ) -> go.Figure:
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            row_heights=[0.65, 0.35],
            subplot_titles=(f"Price — {ticker}", f"Crossover Signal: {strategy.name}"),
        )

        # Row 1: Price
        fig.add_trace(
            go.Scatter(
                x=price.index, y=price,
                mode="lines", name="Price",
                line=dict(color="black", width=1),
                hovertemplate="Price: %{y:,.2f}<extra></extra>",
            ),
            row=1, col=1,
        )

        # MA overlays
        overlay_colors = ["#2196F3", "#FF9800", "#9C27B0", "#4CAF50"]
        for idx, (label, series) in enumerate(ma_overlays.items()):
            color = overlay_colors[idx % len(overlay_colors)]
            fig.add_trace(
                go.Scatter(
                    x=series.index, y=series,
                    mode="lines", name=label,
                    line=dict(color=color, width=1.5, dash="dash"),
                    hovertemplate=f"{label}: %{{y:,.2f}}<extra></extra>",
                ),
                row=1, col=1,
            )

        # Buy/Sell markers on price chart
        buy_dates = buy_signals[buy_signals].index
        sell_dates = sell_signals[sell_signals].index

        if len(buy_dates):
            fig.add_trace(
                go.Scatter(
                    x=buy_dates, y=price.reindex(buy_dates),
                    mode="markers", name="Buy",
                    marker=dict(symbol="triangle-up", size=10, color="green"),
                    hovertemplate="BUY: %{y:,.2f}<extra></extra>",
                ),
                row=1, col=1,
            )
        if len(sell_dates):
            fig.add_trace(
                go.Scatter(
                    x=sell_dates, y=price.reindex(sell_dates),
                    mode="markers", name="Sell",
                    marker=dict(symbol="triangle-down", size=10, color="red"),
                    hovertemplate="SELL: %{y:,.2f}<extra></extra>",
                ),
                row=1, col=1,
            )

        # Row 2: Crossover series
        fig.add_trace(
            go.Scatter(
                x=crossover_series.index, y=crossover_series,
                mode="lines", name="Crossover",
                line=dict(color="blue", width=1.5),
                hovertemplate="Signal: %{y:.4f}<extra></extra>",
            ),
            row=2, col=1,
        )
        fig.add_hline(y=0, line_dash="dot", line_color="gray", row=2, col=1)

        fig.update_layout(height=750, hovermode="x unified", showlegend=True)
        return fig

    def render_results(self, result: AnalysisResult) -> None:
        if result.error:
            st.error(f"❌ [{result.ticker}] {result.error}")
            return

        perf = result.data["performance"]
        pos = result.data["current_position"]
        trades = result.data["trades"]
        fig = result.data["fig"]

        with st.expander(f"📊 {result.ticker} — {result.data['signal_label']}", expanded=True):
            # 1. Current Position
            st.subheader("Current Position")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("In Trade", "Yes ✅" if pos.in_trade else "No ⬜")
            c2.metric("Current Price", f"{pos.current_price:,.2f}")
            if pos.in_trade:
                c3.metric("Unrealized P&L", f"{pos.unrealized_pnl_pct:.2f}%" if pos.unrealized_pnl_pct is not None else "—")
                c4.metric("Days Held", str(pos.days_held) if pos.days_held is not None else "—")
            else:
                c3.metric("Unrealized P&L", "—")
                c4.metric("Days Held", "—")

            regime_label = "Above Zero (Bullish)" if pos.regime == "above_zero" else "Below Zero (Bearish)"
            st.caption(f"Signal: {pos.current_signal_value:.4f} | Regime: {regime_label}")

            st.divider()

            # 2. Performance Summary
            st.subheader("Performance Summary")
            m1, m2, m3 = st.columns(3)
            m1.metric("Win Rate", f"{perf.win_rate:.1f}%")
            m2.metric("Avg Return", f"{perf.avg_return:.2f}%")
            m3.metric(
                "Profit Factor",
                f"{perf.profit_factor:.2f}" if perf.profit_factor != float("inf") else "∞",
            )

            m4, m5, m6 = st.columns(3)
            m4.metric("Total Return", f"{perf.total_return:.2f}%")
            m5.metric(
                "Sharpe Ratio",
                f"{perf.sharpe_ratio:.2f}" if perf.sharpe_ratio is not None else "—",
            )
            m6.metric("Max Consec. Losses", str(perf.max_consecutive_losses))

            m7, m8, m9 = st.columns(3)
            m7.metric("Closed Trades", str(perf.closed_trades))
            m8.metric("Best Trade", f"{perf.best_trade_return:.2f}%")
            m9.metric("Worst Trade", f"{perf.worst_trade_return:.2f}%")

            st.divider()

            # 3. Signal Chart
            with st.expander("📈 Signal Chart", expanded=True):
                try:
                    st.plotly_chart(fig, width="stretch")
                except TypeError:
                    st.plotly_chart(fig, use_container_width=True)

            # 4. Trade Log
            with st.expander("📋 Trade Log", expanded=False):
                if trades:
                    rows = []
                    for t in trades:
                        rows.append({
                            "Entry Date": t.entry_date,
                            "Entry Price": round(t.entry_price, 2),
                            "Exit Date": t.exit_date,
                            "Exit Price": round(t.exit_price, 2) if t.exit_price else None,
                            "Return %": round(t.return_pct, 2) if t.return_pct is not None else None,
                            "Holding Days": t.holding_days,
                            "MAE %": round(t.mae_pct, 2) if t.mae_pct is not None else None,
                            "Status": t.status,
                        })
                    st.dataframe(pd.DataFrame(rows), use_container_width=True)
                else:
                    st.info("No trades generated.")
