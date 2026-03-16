from typing import Any, Dict, List

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.constants import (
    COLOR_ACTIVE,
    COLOR_NEGATIVE,
    COLOR_POSITIVE,
    DATE_FORMAT_DISPLAY,
    fmt_price,
    fmt_pct,
    fmt_pct_signed,
    style_positive_negative,
)

from src.base import AnalysisPack, AnalysisResult
from src.strategy.strategies import BaseStrategy, MACrossoverStrategy, PriceVsMAStrategy
from src.strategy.analytics import (
    build_equity_curve,
    build_trades,
    calculate_drawdown_during_trades,
    calculate_equity_curve_max_drawdown,
    calculate_max_drawdown,
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
            ma_len = col2.number_input("MA Length:", min_value=2, value=50, step=10, key="pma_len")
            col3, col4 = st.sidebar.columns(2)
            buy_lag = col3.number_input("Buy Lag (days):", min_value=0, value=0, step=1, key="pma_buy_lag")
            sell_lag = col4.number_input("Sell Lag (days):", min_value=0, value=2, step=1, key="pma_sell_lag")
            strategy = PriceVsMAStrategy(ma_type, int(ma_len), int(buy_lag), int(sell_lag))

        else:  # MA Crossover
            col1, col2 = st.sidebar.columns(2)
            fast_type = col1.selectbox("Fast MA Type:", ["EMA", "SMA", "WMA"], key="mac_fast_type")
            fast_len = col2.number_input("Fast Length:", min_value=2, value=50, step=10, key="mac_fast_len")
            col3, col4 = st.sidebar.columns(2)
            slow_type = col3.selectbox("Slow MA Type:", ["SMA", "EMA", "WMA"], key="mac_slow_type")
            slow_len = col4.number_input("Slow Length:", min_value=2, value=200, step=10, key="mac_slow_len")
            col5, col6 = st.sidebar.columns(2)
            buy_lag = col5.number_input("Buy Lag:", min_value=0, value=1, step=1, key="mac_buy_lag")
            sell_lag = col6.number_input("Sell Lag:", min_value=0, value=1, step=1, key="mac_sell_lag")
            strategy = MACrossoverStrategy(
                fast_type, int(fast_len), slow_type, int(slow_len), int(buy_lag), int(sell_lag)
            )

        st.sidebar.divider()
        from_date = st.sidebar.date_input(
            "Backtest From Date:",
            value=None,
            help="Leave empty to use all available data. Set a later date to avoid early-data bias (tiny prices → inflated % returns).",
            key="strat_from_date",
        )

        return {"tickers": tickers, "strategy": strategy, "from_date": from_date}

    def run_computation(self, ticker: str, df: pd.DataFrame, config: Dict) -> AnalysisResult:
        strategy: BaseStrategy = config["strategy"]
        from_date = config.get("from_date")

        try:
            # Compute on full df so MAs have full history for warmup
            crossover_series, buy_signals, sell_signals = strategy.compute(df)

            # Trim to from_date (signals already computed — no lookahead)
            if from_date is not None:
                from_ts = pd.Timestamp(from_date)
                df = df[df.index >= from_ts]
                crossover_series = crossover_series[crossover_series.index >= from_ts]
                buy_signals = buy_signals[buy_signals.index >= from_ts]
                sell_signals = sell_signals[sell_signals.index >= from_ts]

            price = df["Close"]

            trades = build_trades(price, buy_signals, sell_signals)
            trades = calculate_drawdown_during_trades(trades, price)
            performance = calculate_trade_performance(trades)
            current_pos = get_current_position(price, crossover_series, buy_signals, sell_signals)
            ma_overlays = strategy.get_ma_overlays(df)

            # Buy & hold stats
            bh_total_return = (float(price.iloc[-1]) / float(price.iloc[0]) - 1) * 100
            bh_max_drawdown = calculate_max_drawdown(price)
            strat_max_drawdown = calculate_equity_curve_max_drawdown(trades)

            # Equity curves
            INITIAL_CAPITAL = 1000.0
            strat_equity = build_equity_curve(price, buy_signals, sell_signals, INITIAL_CAPITAL)
            bh_equity = price / float(price.iloc[0]) * INITIAL_CAPITAL

            fig = self._build_equity_chart(ticker, strat_equity, bh_equity, strategy.name)

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
                    "bh_total_return": bh_total_return,
                    "bh_max_drawdown": bh_max_drawdown,
                    "strat_max_drawdown": strat_max_drawdown,
                    "strat_equity": strat_equity,
                    "bh_equity": bh_equity,
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

    @staticmethod
    def _build_equity_chart(
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
            title=f"Equity Curve — {ticker} (Initial: $1,000)",
            yaxis_title="Position Value (USD)",
            yaxis_type="log" if log_scale else "linear",
            height=500,
            hovermode="x unified",
            showlegend=True,
        )
        return fig

    @staticmethod
    def _render_return_distribution(trades) -> None:
        from src.strategy.analytics import Trade
        closed = [t for t in trades if t.status == "closed" and t.return_pct is not None]
        if len(closed) < 2:
            st.info("Not enough closed trades to show distribution.")
            return

        returns = [t.return_pct for t in closed]
        wins = [r for r in returns if r > 0]
        losses = [r for r in returns if r <= 0]

        # --- Percentile stats table ---
        percentiles = [5, 10, 25, 50, 75, 90, 95]
        rows = []
        for p in percentiles:
            rows.append({"Percentile": f"P{p}", "Return %": fmt_pct(np.percentile(returns, p))})
        rows.append({"Percentile": "Mean", "Return %": fmt_pct(np.mean(returns))})
        rows.append({"Percentile": "Std Dev", "Return %": fmt_pct(np.std(returns, ddof=1))})

        col_stats, col_buckets = st.columns(2)

        with col_stats:
            st.markdown("**Percentile breakdown**")
            st.dataframe(
                pd.DataFrame(rows),
                hide_index=True,
                use_container_width=True,
                height=38 + len(rows) * 35,
            )

        # --- Bucket table ---
        buckets = [
            ("< -20%",   float("-inf"), -20),
            ("-20 → -10%", -20, -10),
            ("-10 → -5%",  -10,  -5),
            ("-5 → 0%",    -5,    0),
            ("0 → 5%",      0,    5),
            ("5 → 10%",     5,   10),
            ("10 → 20%",   10,   20),
            ("> 20%",      20, float("inf")),
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

        # --- Histogram chart ---
        fig = go.Figure()
        if wins:
            fig.add_trace(go.Histogram(
                x=wins, name="Win",
                marker_color="rgba(34, 197, 94, 0.7)",
                xbins=dict(size=2),
            ))
        if losses:
            fig.add_trace(go.Histogram(
                x=losses, name="Loss",
                marker_color="rgba(239, 68, 68, 0.7)",
                xbins=dict(size=2),
            ))

        mean_r = float(np.mean(returns))
        median_r = float(np.median(returns))
        fig.add_vline(x=mean_r, line_dash="dash", line_color="white",
                      annotation_text=f"Mean {mean_r:.1f}%", annotation_position="top right")
        fig.add_vline(x=median_r, line_dash="dot", line_color="yellow",
                      annotation_text=f"Median {median_r:.1f}%", annotation_position="top left")
        fig.add_vline(x=0, line_color="gray", line_width=1)

        fig.update_layout(
            barmode="overlay",
            height=350,
            xaxis_title="Return %",
            yaxis_title="# Trades",
            hovermode="x unified",
            showlegend=True,
            margin=dict(t=30),
        )
        try:
            st.plotly_chart(fig, width="stretch")
        except TypeError:
            st.plotly_chart(fig, use_container_width=True)

    @staticmethod
    def _render_retracement_distribution(trades) -> None:
        """Distribution of retracement from MFE: (mfe_price - exit_price) / mfe_price * 100."""
        closed = [
            t for t in trades
            if t.status == "closed" and t.mfe_price and t.exit_price
        ]
        if len(closed) < 2:
            st.info("Not enough closed trades to show retracement distribution.")
            return

        values = [(t.mfe_price - t.exit_price) / t.mfe_price * 100 for t in closed]

        # --- Percentile stats table ---
        percentiles = [5, 10, 25, 50, 75, 90, 95]
        pct_rows = []
        for p in percentiles:
            pct_rows.append({"Percentile": f"P{p}", "Retracement %": fmt_pct(np.percentile(values, p))})
        pct_rows.append({"Percentile": "Mean",    "Retracement %": fmt_pct(np.mean(values))})
        pct_rows.append({"Percentile": "Std Dev", "Retracement %": fmt_pct(np.std(values, ddof=1))})

        # --- Bucket table (retracement is always ≥ 0) ---
        buckets = [
            ("0 → 5%",     0,  5),
            ("5 → 10%",    5, 10),
            ("10 → 20%",  10, 20),
            ("20 → 30%",  20, 30),
            ("30 → 50%",  30, 50),
            ("> 50%",     50, float("inf")),
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
                "Avg Retracement": fmt_pct(np.mean(subset)) if subset else "—",
            })

        col_stats, col_buckets = st.columns(2)

        with col_stats:
            st.markdown("**Percentile breakdown**")
            st.dataframe(
                pd.DataFrame(pct_rows),
                hide_index=True,
                use_container_width=True,
                height=38 + len(pct_rows) * 35,
            )

        with col_buckets:
            st.markdown("**Retracement buckets**")
            st.dataframe(
                pd.DataFrame(bucket_rows),
                hide_index=True,
                use_container_width=True,
                height=38 + len(bucket_rows) * 35,
            )

        # --- Histogram ---
        mean_v = float(np.mean(values))
        median_v = float(np.median(values))
        fig = go.Figure()
        fig.add_trace(go.Histogram(
            x=values, name="Retracement",
            marker_color="rgba(251, 191, 36, 0.7)",
            xbins=dict(size=2),
        ))
        fig.add_vline(x=mean_v, line_dash="dash", line_color="white",
                      annotation_text=f"Mean {mean_v:.1f}%", annotation_position="top right")
        fig.add_vline(x=median_v, line_dash="dot", line_color="yellow",
                      annotation_text=f"Median {median_v:.1f}%", annotation_position="top left")

        fig.update_layout(
            barmode="overlay",
            height=350,
            xaxis_title="Retracement from MFE (%)",
            yaxis_title="# Trades",
            hovermode="x unified",
            showlegend=False,
            margin=dict(t=30),
        )
        try:
            st.plotly_chart(fig, width="stretch")
        except TypeError:
            st.plotly_chart(fig, use_container_width=True)

    @staticmethod
    def _build_monthly_returns_df(equity: pd.Series) -> pd.DataFrame:
        """
        Given an equity curve, return a year × month DataFrame of monthly returns (%).
        Rows are years descending; columns are Jan..Dec.
        Cells are fmt_pct strings; empty string where no data.
        """
        # Month-end values
        monthly = equity.resample("ME").last()
        # Monthly return: (this month / previous month) - 1
        monthly_ret = monthly.pct_change() * 100
        # Drop the very first NaN (no prior month)
        monthly_ret = monthly_ret.dropna()

        MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

        years = sorted(monthly_ret.index.year.unique(), reverse=True)
        rows = []
        for yr in years:
            row: Dict[str, Any] = {"Year": str(yr)}
            year_monthly_vals = []
            for m_i, m_name in enumerate(MONTHS, start=1):
                mask = (monthly_ret.index.year == yr) & (monthly_ret.index.month == m_i)
                vals = monthly_ret[mask]
                if len(vals) > 0:
                    v = float(vals.iloc[0])
                    row[m_name] = fmt_pct(v)
                    year_monthly_vals.append(v)
                else:
                    row[m_name] = ""

            # Compound annual / YTD return
            if year_monthly_vals:
                compound = 1.0
                for v in year_monthly_vals:
                    compound *= (1 + v / 100)
                row["Annual"] = fmt_pct((compound - 1) * 100)
            else:
                row["Annual"] = ""

            rows.append(row)

        return pd.DataFrame(rows)

    @staticmethod
    def _style_monthly_table(df: pd.DataFrame) -> "pd.io.formats.style.Styler":
        """Green for positive months, red for negative, blank for empty."""
        MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

        def _cell_style(val):
            if not isinstance(val, str) or val == "":
                return ""
            # Strip formatting to get numeric value
            try:
                numeric = float(val.replace(",", "").replace("%", ""))
            except ValueError:
                return ""
            if numeric > 0:
                return COLOR_POSITIVE
            elif numeric < 0:
                return COLOR_NEGATIVE
            return ""

        color_cols = [c for c in MONTHS + ["Annual"] if c in df.columns]
        return df.style.applymap(_cell_style, subset=color_cols)

    @staticmethod
    def _build_monthly_stats_df(equity: pd.Series) -> pd.DataFrame:
        """
        For each calendar month (Jan–Dec), compute percentile distribution across all years.
        Rows = months, columns = P95, P90, P80, P70, P60, P50, P40, P30, P20, P10, P5.
        """
        MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                       "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        PERCENTILES = [95, 90, 80, 70, 60, 50, 40, 30, 20, 10, 5]

        monthly = equity.resample("ME").last()
        monthly_ret = monthly.pct_change().dropna() * 100

        rows = []
        for m_i, m_name in enumerate(MONTH_NAMES, start=1):
            vals = monthly_ret[monthly_ret.index.month == m_i].tolist()
            row: Dict[str, Any] = {"Month": m_name}
            if vals:
                for p in PERCENTILES:
                    row[f"P{p}"] = fmt_pct(float(np.percentile(vals, p)))
            else:
                for p in PERCENTILES:
                    row[f"P{p}"] = "—"
            rows.append(row)
        return pd.DataFrame(rows)

    @staticmethod
    def _style_monthly_stats_df(df: pd.DataFrame) -> "pd.io.formats.style.Styler":
        """Colour percentile cells by sign."""
        PERCENTILES = [95, 90, 80, 70, 60, 50, 40, 30, 20, 10, 5]
        color_cols = [f"P{p}" for p in PERCENTILES if f"P{p}" in df.columns]

        def _cell_style(val):
            if not isinstance(val, str) or val == "—":
                return ""
            try:
                numeric = float(val.replace(",", "").replace("%", ""))
            except ValueError:
                return ""
            if numeric > 0:
                return COLOR_POSITIVE
            elif numeric < 0:
                return COLOR_NEGATIVE
            return ""

        return df.style.applymap(_cell_style, subset=color_cols)

    @staticmethod
    def _render_monthly_returns_tables(
        strat_equity: pd.Series,
        bh_equity: pd.Series,
        ticker: str,
    ) -> None:
        st.subheader("📅 Monthly Returns — Strategy Position")
        strat_df = StrategyBacktestPack._build_monthly_returns_df(strat_equity)
        if strat_df.empty:
            st.info("Not enough data for monthly breakdown.")
        else:
            n = len(strat_df)
            st.dataframe(
                StrategyBacktestPack._style_monthly_table(strat_df),
                hide_index=True,
                use_container_width=True,
                height=38 + n * 35,
            )

        st.subheader("📅 Monthly Returns — Buy & Hold Position")
        bh_df = StrategyBacktestPack._build_monthly_returns_df(bh_equity)
        if bh_df.empty:
            st.info("Not enough data for monthly breakdown.")
        else:
            n = len(bh_df)
            st.dataframe(
                StrategyBacktestPack._style_monthly_table(bh_df),
                hide_index=True,
                use_container_width=True,
                height=38 + n * 35,
            )

        st.divider()

        st.subheader("📊 Monthly Statistics — Strategy Position")
        strat_stats = StrategyBacktestPack._build_monthly_stats_df(strat_equity)
        st.dataframe(
            StrategyBacktestPack._style_monthly_stats_df(strat_stats),
            hide_index=True,
            use_container_width=True,
            height=38 + 12 * 35,
        )

        st.subheader("📊 Monthly Statistics — Buy & Hold Position")
        bh_stats = StrategyBacktestPack._build_monthly_stats_df(bh_equity)
        st.dataframe(
            StrategyBacktestPack._style_monthly_stats_df(bh_stats),
            hide_index=True,
            use_container_width=True,
            height=38 + 12 * 35,
        )

    def render_results(self, result: AnalysisResult) -> None:
        if result.error:
            st.error(f"❌ [{result.ticker}] {result.error}")
            return

        perf = result.data["performance"]
        pos = result.data["current_position"]
        trades = result.data["trades"]
        fig = result.data["fig"]
        bh_total_return: float = result.data.get("bh_total_return", 0.0)
        bh_max_drawdown: float = result.data.get("bh_max_drawdown", 0.0)
        strat_max_drawdown: float = result.data.get("strat_max_drawdown", 0.0)

        with st.expander(f"📊 {result.ticker} — {result.data['signal_label']}", expanded=True):
            # 1. Current Position
            st.subheader("Current Position")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("In Trade", "Yes ✅" if pos.in_trade else "No ⬜")
            c2.metric("Current Price", f"{pos.current_price:,.0f}")
            if pos.in_trade:
                c3.metric("Unrealized P&L", fmt_pct(pos.unrealized_pnl_pct) if pos.unrealized_pnl_pct is not None else "—")
                c4.metric("Days Held", str(pos.days_held) if pos.days_held is not None else "—")
            else:
                c3.metric("Unrealized P&L", "—")
                c4.metric("Days Held", "—")

            regime_label = "Above Zero (Bullish)" if pos.regime == "above_zero" else "Below Zero (Bearish)"
            st.caption(f"Signal: {pos.current_signal_value:.4f} | Regime: {regime_label}")

            st.divider()

            # 2. Performance Summary
            st.subheader("Performance Summary")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Win Rate", fmt_pct(perf.win_rate))
            m2.metric("Avg Win", fmt_pct(perf.avg_winning_return) if perf.avg_winning_return else "—")
            m3.metric("Avg Loss", fmt_pct(perf.avg_losing_return) if perf.avg_losing_return else "—")
            m4.metric(
                "Profit Factor",
                f"{perf.profit_factor:.2f}" if perf.profit_factor != float("inf") else "∞",
            )

            m5, m6, m7, m8 = st.columns(4)
            m5.metric("Total Return", fmt_pct(perf.total_return))
            m6.metric("Sharpe", f"{perf.sharpe_ratio:.2f}" if perf.sharpe_ratio is not None else "—")
            m7.metric("Sortino", f"{perf.sortino_ratio:.2f}" if perf.sortino_ratio is not None else "—")
            m8.metric("Max Consec. Losses", str(perf.max_consecutive_losses))

            m9, m10, m11 = st.columns(3)
            m9.metric("Closed Trades", str(perf.closed_trades))
            m10.metric("Best Trade", fmt_pct(perf.best_trade_return))
            m11.metric("Worst Trade", fmt_pct(perf.worst_trade_return))

            st.divider()

            # 3. Strategy vs Buy & Hold
            st.subheader("📈 Strategy vs Buy & Hold")
            cmp_data = {
                "Metric":        ["Total Return (%)", "Max Drawdown (%)"],
                "Strategy":      [fmt_pct(perf.total_return), fmt_pct(strat_max_drawdown)],
                "Buy & Hold":    [fmt_pct(bh_total_return),   fmt_pct(bh_max_drawdown)],
                "Difference":    [
                    fmt_pct_signed(perf.total_return - bh_total_return),
                    fmt_pct_signed(strat_max_drawdown - bh_max_drawdown),
                ],
            }
            st.dataframe(
                pd.DataFrame(cmp_data),
                hide_index=True,
                use_container_width=True,
                height=38 + 2 * 35,
            )

            st.divider()

            # 4. Trade Log (above chart, no expander)
            st.subheader("📋 Trade Log")
            if trades:
                sorted_trades = sorted(trades, key=lambda x: x.entry_date, reverse=True)
                rows = []
                for t in sorted_trades:
                    rows.append({
                        "Entry Date": t.entry_date.strftime(DATE_FORMAT_DISPLAY),
                        "Entry Price": fmt_price(t.entry_price),
                        "Exit Date": t.exit_date.strftime(DATE_FORMAT_DISPLAY) if t.exit_date else "—",
                        "Exit Price": fmt_price(t.exit_price) if t.exit_price else "—",
                        "Return %": fmt_pct(t.return_pct) if t.return_pct is not None else "—",
                        "Holding Days": t.holding_days,
                        "MAE %": fmt_pct(t.mae_pct) if t.mae_pct is not None else "—",
                        "MAE Price": fmt_price(t.mae_price) if t.mae_price is not None else "—",
                        "MFE %": fmt_pct(t.mfe_pct) if t.mfe_pct is not None else "—",
                        "MFE Price": fmt_price(t.mfe_price) if t.mfe_price is not None else "—",
                        "Retracement %": fmt_pct((t.mfe_price - t.exit_price) / t.mfe_price * 100)
                            if (t.mfe_price and t.exit_price) else "—",
                        "Status": t.status,
                    })
                trade_df = pd.DataFrame(rows)

                # Row colouring: open → active gold; |return| ≤ 1% → no colour; else green/red
                returns_numeric = [t.return_pct for t in sorted_trades]
                statuses = [t.status for t in sorted_trades]

                def _trade_row_style(row: pd.Series):
                    if statuses[row.name] == "open":
                        return [COLOR_ACTIVE] * len(row)
                    return [style_positive_negative(returns_numeric[row.name], threshold=1.0)] * len(row)

                styled_trades = trade_df.style.apply(_trade_row_style, axis=1)
                n_rows = len(trade_df)
                height = 38 + min(n_rows, 20) * 35
                st.dataframe(styled_trades, use_container_width=True, hide_index=True, height=height)
            else:
                st.info("No trades generated.")

            st.divider()

            # 4. Return Distribution
            st.subheader("📊 Return Distribution")
            self._render_return_distribution(trades)

            st.divider()

            # 5. Retracement from Peak Distribution
            st.subheader("📉 Retracement from Peak (MFE) Distribution")
            self._render_retracement_distribution(trades)

            st.divider()

            # 6. Equity Curve
            with st.expander("📈 Equity Curve", expanded=True):
                log_scale = st.checkbox(
                    "Log scale (Y axis)",
                    value=False,
                    key=f"strat_log_scale_{result.ticker}",
                )
                strat_equity = result.data.get("strat_equity")
                bh_equity = result.data.get("bh_equity")
                equity_fig = self._build_equity_chart(
                    result.ticker, strat_equity, bh_equity,
                    result.data["signal_label"], log_scale,
                )
                try:
                    st.plotly_chart(equity_fig, width="stretch")
                except TypeError:
                    st.plotly_chart(equity_fig, use_container_width=True)

            st.divider()

            # 6. Monthly Returns Tables
            strat_equity = result.data.get("strat_equity")
            bh_equity = result.data.get("bh_equity")
            self._render_monthly_returns_tables(strat_equity, bh_equity, result.ticker)
