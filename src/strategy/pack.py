from datetime import datetime as _dt
from typing import Any, Dict

import pandas as pd
import streamlit as st

from src.constants import (
    COLOR_ACTIVE,
    DATE_FORMAT_DISPLAY,
    INITIAL_CAPITAL,
    YFINANCE_PRESETS,
    fmt_capture,
    fmt_equity,
    fmt_price,
    fmt_pct,
    style_capture,
    style_positive_negative,
)
from src.ui import plot_chart

from src.base import AnalysisPack, AnalysisResult
from src.strategy.strategies import BaseStrategy, MACrossoverStrategy, PriceVsMAStrategy
from src.strategy.analytics import (
    Trade,
    build_equity_curve,
    build_trades,
    calculate_drawdown_during_trades,
    calculate_equity_curve_max_drawdown,
    calculate_max_drawdown,
    calculate_trade_performance,
    get_current_position,
)
from src.strategy.charts import build_equity_chart
from src.strategy.renderers import (
    render_deterioration_section,
    render_monthly_returns_tables,
    render_nonneg_distribution,
    render_return_distribution,
)


# ---------------------------------------------------------------------------
# Strategy pack
# ---------------------------------------------------------------------------


class StrategyBacktestPack(AnalysisPack):
    @property
    def pack_name(self) -> str:
        return "Strategy Backtest"

    def render_sidebar(self) -> Dict[str, Any]:
        return self.render_strategy_sidebar(key_prefix="strat", header="Strategy Backtest")

    @staticmethod
    def render_strategy_sidebar(key_prefix: str = "strat", header: str = "Strategy Backtest") -> Dict[str, Any]:
        """
        Render the full strategy sidebar and return a config dict.
        key_prefix keeps Streamlit widget keys unique across pages.
        """
        st.sidebar.header(header)

        data_source = st.sidebar.selectbox(
            "Data Source:",
            ["yfinance", "vnstock"],
            key=f"{key_prefix}_data_source",
            help="yfinance: global tickers (BTC-USD, AAPL…) | vnstock: Vietnamese stocks (VCB, VIC…)",
        )
        VNSTOCK_GROUPS = ["— type manually —", "VN30", "VN100", "VNMidCap"]
        YFINANCE_GROUPS = ["— type manually —"] + list(YFINANCE_PRESETS.keys())
        groups = VNSTOCK_GROUPS if data_source == "vnstock" else YFINANCE_GROUPS

        # Reset group selection when data source changes so the previous source's
        # group choice doesn't carry over into the new source's option list.
        group_key = f"{key_prefix}_symbol_group"
        prev_ds_key = f"{key_prefix}_symbol_group_ds"
        if st.session_state.get(prev_ds_key) != data_source:
            st.session_state[group_key] = 0
            st.session_state[prev_ds_key] = data_source

        group_choice = st.sidebar.selectbox(
            "Symbol Group:",
            groups,
            key=group_key,
        )

        if data_source == "vnstock" and group_choice != "— type manually —":
            from src.data_loader import load_vnstock_group
            tickers = load_vnstock_group(group_choice)
            st.sidebar.caption(f"{len(tickers)} symbols from {group_choice}")
        elif data_source == "yfinance" and group_choice != "— type manually —":
            tickers = YFINANCE_PRESETS[group_choice]
            st.sidebar.caption(f"{len(tickers)} symbols from {group_choice}")
        else:
            default_ticker = "BTC-USD" if data_source == "yfinance" else "VCB"
            ticker_input = st.sidebar.text_input(
                "Tickers (space-separated):",
                value=default_ticker,
                key=f"{key_prefix}_ticker_input",
            )
            tickers = [t.strip().upper() for t in ticker_input.split() if t.strip()]

        strategy_type = st.sidebar.selectbox(
            "Strategy Type:",
            ["Price vs MA", "MA Crossover"],
            key=f"{key_prefix}_type",
        )

        if strategy_type == "Price vs MA":
            col1, col2 = st.sidebar.columns(2)
            ma_type = col1.selectbox("MA Type:", ["SMA", "EMA", "WMA"], key=f"{key_prefix}_pma_type")
            ma_len = col2.number_input("MA Length:", min_value=2, value=50, step=10, key=f"{key_prefix}_pma_len")
            col3, col4 = st.sidebar.columns(2)
            buy_lag = col3.number_input("Buy Lag (days):", min_value=0, value=0, step=1, key=f"{key_prefix}_pma_buy_lag")
            sell_lag = col4.number_input("Sell Lag (days):", min_value=0, value=2, step=1, key=f"{key_prefix}_pma_sell_lag")
            strategy = PriceVsMAStrategy(ma_type, int(ma_len), int(buy_lag), int(sell_lag))

        else:  # MA Crossover
            col1, col2 = st.sidebar.columns(2)
            fast_type = col1.selectbox("Fast MA Type:", ["EMA", "SMA", "WMA"], key=f"{key_prefix}_mac_fast_type")
            fast_len = col2.number_input("Fast Length:", min_value=2, value=50, step=10, key=f"{key_prefix}_mac_fast_len")
            col3, col4 = st.sidebar.columns(2)
            slow_type = col3.selectbox("Slow MA Type:", ["SMA", "EMA", "WMA"], key=f"{key_prefix}_mac_slow_type")
            slow_len = col4.number_input("Slow Length:", min_value=2, value=200, step=10, key=f"{key_prefix}_mac_slow_len")
            col5, col6 = st.sidebar.columns(2)
            buy_lag = col5.number_input("Buy Lag:", min_value=0, value=1, step=1, key=f"{key_prefix}_mac_buy_lag")
            sell_lag = col6.number_input("Sell Lag:", min_value=0, value=1, step=1, key=f"{key_prefix}_mac_sell_lag")
            strategy = MACrossoverStrategy(
                fast_type, int(fast_len), slow_type, int(slow_len), int(buy_lag), int(sell_lag)
            )

        st.sidebar.divider()
        from_date = st.sidebar.date_input(
            "Backtest From Date:",
            value=None,
            help="Leave empty to use all available data. Set a later date to avoid early-data bias (tiny prices → inflated % returns).",
            key=f"{key_prefix}_from_date",
        )

        return {
            "tickers": tickers,
            "strategy": strategy,
            "from_date": from_date,
            "data_source": data_source,
            "vnstock_source": "KBS",
            "symbol_group": group_choice,
        }

    @staticmethod
    def _compute_ticker_core(ticker: str, df: pd.DataFrame, config: Dict) -> Dict[str, Any]:
        """
        Pure computation — no Streamlit calls.
        Returns a dict with all computed values needed by both single and batch rendering.
        """
        strategy: BaseStrategy = config["strategy"]
        from_date = config.get("from_date")

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

        bh_total_return = (float(price.iloc[-1]) / float(price.iloc[0]) - 1) * 100
        bh_max_drawdown = calculate_max_drawdown(price)
        strat_max_drawdown = calculate_equity_curve_max_drawdown(trades)

        strat_equity = build_equity_curve(price, buy_signals, sell_signals, INITIAL_CAPITAL)
        bh_equity = price / float(price.iloc[0]) * INITIAL_CAPITAL

        # Stamp equity_at_close on each closed trade — single source of truth,
        # derived from trade returns rather than looked up from the equity curve.
        capital = INITIAL_CAPITAL
        for t in sorted((t for t in trades if t.status == "closed"), key=lambda x: x.entry_date):
            capital *= (1 + t.return_pct / 100)
            t.equity_at_close = capital

        return {
            "price": price,
            "crossover_series": crossover_series,
            "trades": trades,
            "performance": performance,
            "current_position": current_pos,
            "ma_overlays": ma_overlays,
            "signal_label": strategy.name,
            "bh_total_return": bh_total_return,
            "bh_max_drawdown": bh_max_drawdown,
            "strat_max_drawdown": strat_max_drawdown,
            "strat_equity": strat_equity,
            "bh_equity": bh_equity,
        }

    def run_computation(self, ticker: str, df: pd.DataFrame, config: Dict) -> AnalysisResult:
        try:
            core = self._compute_ticker_core(ticker, df, config)
            fig = build_equity_chart(
                ticker, core["strat_equity"], core["bh_equity"], core["signal_label"]
            )
            return AnalysisResult(
                ticker=ticker,
                pack_name=self.pack_name,
                price_series=core["price"],
                signal_series=core["crossover_series"],
                data={**core, "fig": fig},
            )
        except Exception as e:
            return AnalysisResult(
                ticker=ticker,
                pack_name=self.pack_name,
                price_series=df["Close"] if "Close" in df.columns else pd.Series(dtype=float),
                signal_series=pd.Series(dtype=float),
                error=str(e),
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
            # 0. Data summary
            price = result.price_series
            st.caption(
                f"Ngày thống kê: {_dt.now().strftime(DATE_FORMAT_DISPLAY)}  |  "
                f"Ngày dữ liệu đầu tiên: {price.index.min().strftime(DATE_FORMAT_DISPLAY)}  |  "
                f"Ngày dữ liệu cuối cùng: {price.index[-1].strftime(DATE_FORMAT_DISPLAY)}  |  "
                f"Tổng số phiên giao dịch: {len(price):,}"
            )

            st.divider()

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
            m1, m2, m3 = st.columns(3)
            m1.metric("Win Rate", fmt_pct(perf.win_rate))
            m2.metric("Avg Win", fmt_pct(perf.avg_winning_return) if perf.avg_winning_return else "—")
            m3.metric("Avg Loss", fmt_pct(perf.avg_losing_return) if perf.avg_losing_return else "—")

            m5, m6 = st.columns(2)
            m5.metric("Total Return", fmt_pct(perf.total_return))
            m6.metric("Max Consec. Losses", str(perf.max_consecutive_losses))

            m9, m10, m11, m12, m13 = st.columns(5)
            m9.metric("Closed Trades", str(perf.closed_trades))
            m10.metric("Win Trades", str(perf.win_count))
            m11.metric("Loss Trades", str(perf.loss_count))
            m12.metric("Best Trade", fmt_pct(perf.best_trade_return))
            m13.metric("Worst Trade", fmt_pct(perf.worst_trade_return))

            st.divider()

            # 3. Strategy vs Buy & Hold
            st.subheader("📈 Strategy vs Buy & Hold")
            capture = perf.total_return / bh_total_return if bh_total_return and bh_total_return > 0 else None
            cmp_data = {
                "Metric":      ["Total Return (%)", "Max Drawdown (%)"],
                "Strategy":    [fmt_pct(perf.total_return), fmt_pct(strat_max_drawdown)],
                "Buy & Hold":  [fmt_pct(bh_total_return),  fmt_pct(bh_max_drawdown)],
                "Capture":     [fmt_capture(capture),       ""],
            }
            cmp_df = pd.DataFrame(cmp_data)
            styled_cmp = cmp_df.style.applymap(style_capture, subset=["Capture"])
            st.dataframe(styled_cmp, hide_index=True, use_container_width=True, height=38 + 2 * 35)

            st.divider()

            # 4. Trade Log
            st.subheader("📋 Trade Log")
            if trades:
                bh_equity = result.data.get("bh_equity")
                sorted_trades = sorted(trades, key=lambda x: x.entry_date, reverse=True)
                rows = []
                for t in sorted_trades:
                    eq_close = t.equity_at_close / 1000 if t.equity_at_close is not None else None
                    if t.exit_date is not None and bh_equity is not None:
                        bh_close = float(bh_equity.asof(pd.Timestamp(t.exit_date))) / 1000
                    else:
                        bh_close = None

                    rows.append({
                        "Entry Date": t.entry_date.strftime(DATE_FORMAT_DISPLAY),
                        "Entry Price": fmt_price(t.entry_price),
                        "Exit Date": t.exit_date.strftime(DATE_FORMAT_DISPLAY) if t.exit_date else "—",
                        "Exit Price": fmt_price(t.exit_price) if t.exit_price else "—",
                        "Return %": fmt_pct(t.return_pct) if t.return_pct is not None else "—",
                        "Equity at Close": fmt_equity(eq_close) if eq_close is not None else "—",
                        "B&H at Close": fmt_equity(bh_close) if bh_close is not None else "—",
                        "Holding": t.holding_days,
                        "MAE %": fmt_pct(t.mae_pct) if t.mae_pct is not None else "—",
                        "MAE Price": fmt_price(t.mae_price) if t.mae_price is not None else "—",
                        "MFE %": fmt_pct(t.mfe_pct) if t.mfe_pct is not None else "—",
                        "MFE Price": fmt_price(t.mfe_price) if t.mfe_price is not None else "—",
                        "Retracement %": fmt_pct((t.mfe_price - t.exit_price) / t.mfe_price * 100)
                            if (t.mfe_price and t.exit_price) else "—",
                        "Status": t.status,
                    })
                trade_df = pd.DataFrame(rows)

                returns_numeric = [t.return_pct for t in sorted_trades]
                statuses = [t.status for t in sorted_trades]

                def _trade_row_style(row: pd.Series):
                    if statuses[row.name] == "open":
                        return [COLOR_ACTIVE] * len(row)
                    return [style_positive_negative(returns_numeric[row.name])] * len(row)

                styled_trades = trade_df.style.apply(_trade_row_style, axis=1)
                n_rows = len(trade_df)
                height = 38 + min(n_rows, 20) * 35
                st.dataframe(styled_trades, use_container_width=True, hide_index=True, height=height)
            else:
                st.info("No trades generated.")

            st.divider()

            # 5. Return Distribution
            st.subheader("📊 Return Distribution")
            render_return_distribution(trades)

            st.divider()

            # 6. MAE & MFE of winning trades
            winners = [t for t in trades if t.status == "closed" and t.return_pct is not None and t.return_pct > 0]
            st.subheader("📉 MAE of Winning Trades")
            st.caption("How far winning trades drew down before recovering. Use this to calibrate stop-loss levels: if your open trade exceeds the P90–P95 MAE of winners, it is statistically unlikely to recover.")
            mae_vals = [t.mae_pct for t in winners if t.mae_pct is not None]
            render_nonneg_distribution(mae_vals, "MAE %", "rgba(239, 68, 68, 0.7)")

            st.divider()

            st.subheader("📈 MFE of Winning Trades")
            st.caption("Peak unrealized gain reached during winning trades. Use this to calibrate take-profit levels.")
            mfe_vals = [t.mfe_pct for t in winners if t.mfe_pct is not None]
            render_nonneg_distribution(mfe_vals, "MFE %", "rgba(34, 197, 94, 0.7)")

            st.divider()

            # 7. Equity Curve
            with st.expander("📈 Equity Curve", expanded=True):
                log_scale = st.checkbox(
                    "Log scale (Y axis)",
                    value=False,
                    key=f"strat_log_scale_{result.ticker}",
                )
                strat_equity = result.data.get("strat_equity")
                bh_equity = result.data.get("bh_equity")
                equity_fig = build_equity_chart(
                    result.ticker, strat_equity, bh_equity,
                    result.data["signal_label"], log_scale,
                )
                plot_chart(equity_fig)

            st.divider()

            # 8. Monthly Returns Tables
            strat_equity = result.data.get("strat_equity")
            bh_equity = result.data.get("bh_equity")
            render_monthly_returns_tables(strat_equity, bh_equity, result.ticker, trades)

            st.divider()

            # 9. Strategy Health Over Time
            render_deterioration_section(trades, strat_equity, result.ticker)
