from datetime import datetime as _dt
from typing import Any, Dict, Optional

import pandas as pd
import streamlit as st

from src.constants import (
    COLOR_ACTIVE,
    DATE_FORMAT_DISPLAY,
    INITIAL_CAPITAL,
    NONNEG_BUCKETS,
    RETURN_BUCKETS,
)
from src.fmt import fmt_capture, fmt_equity, fmt_pct, fmt_price
from src.styling import style_capture, style_positive_negative
from src.ui import plot_chart, sidebar_data_source, sidebar_from_date, sidebar_ticker_input

from src.base import AnalysisPack, AnalysisResult
from src.strategy.strategies import BaseStrategy, BollingerBandStrategy, DonchianBreakoutStrategy, MACrossoverStrategy, PriceVsMAStrategy
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
    render_distribution,
    render_monthly_returns_tables,
    render_performance_summary,
)


# ---------------------------------------------------------------------------
# Cached computation — module-level so @st.cache_data works
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600, show_spinner=False)
def compute_ticker_core(
    ticker: str,
    df: pd.DataFrame,
    _strategy: BaseStrategy,
    strategy_key: str,
    from_date: Optional[object] = None,
) -> Dict[str, Any]:
    """
    Pure computation — no Streamlit calls.
    Returns a dict with all computed values needed by both single and batch rendering.
    """
    # Compute on full df so MAs have full history for warmup
    crossover_series, buy_signals, sell_signals = _strategy.compute(df)

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
    overlays = _strategy.get_overlays(df)

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
        "overlays": overlays,
        "signal_label": strategy_key,
        "bh_total_return": bh_total_return,
        "bh_max_drawdown": bh_max_drawdown,
        "strat_max_drawdown": strat_max_drawdown,
        "strat_equity": strat_equity,
        "bh_equity": bh_equity,
    }


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

        data_source = sidebar_data_source(key_prefix)
        tickers = sidebar_ticker_input(data_source, key_prefix, multi=True)

        group_choice = "— type manually —"  # default for config compat

        strategy_type = st.sidebar.selectbox(
            "Strategy Type:",
            ["Price vs MA", "MA Crossover", "Donchian Breakout", "Bollinger Bands"],
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

        elif strategy_type == "MA Crossover":
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

        elif strategy_type == "Donchian Breakout":
            col1, col2 = st.sidebar.columns(2)
            entry_len = col1.number_input("Entry Length:", min_value=2, value=20, step=5, key=f"{key_prefix}_don_entry")
            exit_len = col2.number_input("Exit Length:", min_value=2, value=10, step=5, key=f"{key_prefix}_don_exit")
            strategy = DonchianBreakoutStrategy(int(entry_len), int(exit_len))

        else:  # Bollinger Bands
            col1, col2 = st.sidebar.columns(2)
            bb_period = col1.number_input("Period:", min_value=5, value=20, step=1, key=f"{key_prefix}_bb_period")
            bb_std = col2.number_input("Std Dev:", min_value=0.5, value=2.0, step=0.25, format="%.2f", key=f"{key_prefix}_bb_std")
            strategy = BollingerBandStrategy(int(bb_period), float(bb_std))

        from_date = sidebar_from_date(key_prefix)

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
        """Delegate to the cached module-level function."""
        strategy = config["strategy"]
        return compute_ticker_core(
            ticker, df, strategy, strategy.name, config.get("from_date"),
        )

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
            render_performance_summary(perf, strat_max_drawdown)

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
                    eq_close = t.equity_at_close
                    if t.exit_date is not None and bh_equity is not None:
                        bh_close = float(bh_equity.asof(pd.Timestamp(t.exit_date)))
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
            closed = [t for t in trades if t.status == "closed" and t.return_pct is not None]
            render_distribution([t.return_pct for t in closed], "Return", RETURN_BUCKETS, bucket_header="Return buckets")

            st.divider()

            # 6. MAE & MFE of winning trades
            winners = [t for t in trades if t.status == "closed" and t.return_pct is not None and t.return_pct > 0]
            st.subheader("📉 MAE of Winning Trades")
            st.caption("How far winning trades drew down before recovering. Use this to calibrate stop-loss levels: if your open trade exceeds the P90–P95 MAE of winners, it is statistically unlikely to recover.")
            mae_vals = [t.mae_pct for t in winners if t.mae_pct is not None]
            render_distribution(mae_vals, "MAE %", NONNEG_BUCKETS)

            st.divider()

            st.subheader("📈 MFE of Winning Trades")
            st.caption("Peak unrealized gain reached during winning trades. Use this to calibrate take-profit levels.")
            mfe_vals = [t.mfe_pct for t in winners if t.mfe_pct is not None]
            render_distribution(mfe_vals, "MFE %", NONNEG_BUCKETS)

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
