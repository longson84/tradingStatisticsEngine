"""Position backtest pack (was StrategyBacktestPack)."""
from typing import Any, Dict

import pandas as pd
import streamlit as st

from src.shared.base import BasePack, PackResult
from src.shared.constants import COLOR_ACTIVE, NONNEG_BUCKETS, RETURN_BUCKETS
from src.shared.fmt import fmt_capture, fmt_equity, fmt_pct, fmt_price
from src.shared.report_blocks import build_report_time_range_info

from src.strategy.registry import STRATEGY_NAMES, STRATEGY_REGISTRY
from src.backtest.charts import build_equity_chart
from src.backtest.tables import build_trade_log_df

from src.app.ui import plot_chart, sidebar_data_source, sidebar_from_date, sidebar_ticker_input
from src.app.styling import style_capture, style_positive_negative
from src.app.strategy_sidebar_factories import SIDEBAR_REGISTRY
from src.app.strategy_compute import compute_ticker_core

# Import renderers (these are still Streamlit-based)
from src.app.packs._renderers import (
    render_performance_summary,
    render_distribution,
    render_monthly_returns_tables,
    render_deterioration_section,
)


class PositionPack(BasePack):
    @property
    def pack_name(self) -> str:
        return "Strategy Backtest"

    def render_sidebar(self) -> Dict[str, Any]:
        return self.render_strategy_sidebar(key_prefix="strat", header="Strategy Backtest")

    @staticmethod
    def render_strategy_sidebar(key_prefix: str = "strat", header: str = "Strategy Backtest") -> Dict[str, Any]:
        st.sidebar.header(header)

        data_source = sidebar_data_source(key_prefix)
        tickers = sidebar_ticker_input(data_source, key_prefix, multi=True)

        group_choice = "— type manually —"

        strategy_type = st.sidebar.selectbox(
            "Strategy Type:", STRATEGY_NAMES, key=f"{key_prefix}_type",
        )
        strategy = SIDEBAR_REGISTRY[strategy_type](key_prefix)

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
    def _compute_ticker_core(price: pd.DataFrame, config: Dict) -> Dict[str, Any]:
        strategy = config["strategy"]
        return compute_ticker_core(
            price, strategy, strategy.name, config.get("from_date"),
        )

    def run_computation(self, ticker: str, price: pd.DataFrame, config: Dict) -> PackResult:
        try:
            core = self._compute_ticker_core(ticker, price, config)
            fig = build_equity_chart(
                ticker, core["strat_equity"], core["bh_equity"], core["strategy_label"]
            )
            return PackResult(
                ticker=ticker,
                pack_name=self.pack_name,
                price_series=core["price"],
                signal_series=core["crossover_series"],
                data={**core, "fig": fig},
            )
        except Exception as e:
            return PackResult(
                ticker=ticker,
                pack_name=self.pack_name,
                price_series=price["Close"] if "Close" in price.columns else pd.Series(dtype=float),
                signal_series=pd.Series(dtype=float),
                error=str(e),
            )

    def render_results(self, result: PackResult) -> None:
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

        with st.expander(f"📊 {result.ticker} — {result.data['strategy_label']}", expanded=True):
            price = result.price_series
            st.caption("  |  ".join(build_report_time_range_info(price)[1:]))

            st.divider()

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
            st.caption(f"Signal: {pos.crossover_value:.4f} | Regime: {regime_label}")

            st.divider()

            st.subheader("Performance Summary")
            render_performance_summary(perf, strat_max_drawdown)

            st.divider()

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

            st.subheader("📋 Trade Log")
            if trades:
                bh_equity = result.data.get("bh_equity")
                trade_df = build_trade_log_df(trades, bh_equity)
                sorted_trades = sorted(trades, key=lambda x: x.entry_date, reverse=True)
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

            st.subheader("📊 Return Distribution")
            closed = [t for t in trades if t.status == "closed" and t.return_pct is not None]
            render_distribution([t.return_pct for t in closed], "Return", RETURN_BUCKETS, bucket_header="Return buckets")

            st.divider()

            winners = [t for t in trades if t.status == "closed" and t.return_pct is not None and t.return_pct > 0]
            st.subheader("📉 MAE of Winning Trades")
            st.caption("How far winning trades drew down before recovering.")
            mae_vals = [t.mae_pct for t in winners if t.mae_pct is not None]
            render_distribution(mae_vals, "MAE %", NONNEG_BUCKETS)

            st.divider()

            st.subheader("📈 MFE of Winning Trades")
            st.caption("Peak unrealized gain reached during winning trades.")
            mfe_vals = [t.mfe_pct for t in winners if t.mfe_pct is not None]
            render_distribution(mfe_vals, "MFE %", NONNEG_BUCKETS)

            st.divider()

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
                    result.data["strategy_label"], log_scale,
                )
                plot_chart(equity_fig)

            st.divider()

            strat_equity = result.data.get("strat_equity")
            bh_equity = result.data.get("bh_equity")
            render_monthly_returns_tables(strat_equity, bh_equity, result.ticker, trades)

            st.divider()

            render_deterioration_section(trades, strat_equity, result.ticker)
