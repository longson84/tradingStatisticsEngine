"""Parameter Sweep pack — compare strategy parameters on a single ticker."""
from datetime import datetime
from typing import Any, Dict, List, Tuple

import pandas as pd
import streamlit as st

from src.shared.base import AnalysisResult
from src.shared.constants import (
    COLOR_ACTIVE,
    DATE_FORMAT_DISPLAY,
    NONNEG_BUCKETS,
    RETURN_BUCKETS,
    SUMMARY_PERCENTILES,
)
from src.shared.fmt import fmt_capture, fmt_equity, fmt_pct, fmt_price
from src.app.styling import style_capture, style_positive_negative
from src.backtest.utils import compute_summary_percentiles
from src.backtest.charts import (
    build_boxplot_chart,
    build_drawdown_chart,
    build_return_chart,
    build_trade_count_chart,
    build_win_rate_chart,
)

from src.strategy.registry import STRATEGY_NAMES
from src.app.packs.position_pack import PositionPack
from src.app.packs._renderers import (
    render_deterioration_section,
    render_distribution,
    render_monthly_returns_tables,
    render_performance_summary,
)
from src.app.strategy_sidebar_factories import (
    SWEEP_SIDEBAR_REGISTRY,
    build_from_sweep_config,
    should_skip_sweep_length,
    sweep_label,
)
from src.app.ui import plot_chart, sidebar_data_source, sidebar_from_date, sidebar_ticker_input


class ParameterSweepPack(PositionPack):
    @property
    def pack_name(self) -> str:
        return "Parameter Sweep"

    def render_sidebar(self) -> Dict[str, Any]:
        st.sidebar.header("Parameter Sweep")

        data_source = sidebar_data_source("sweep")
        ticker = sidebar_ticker_input(data_source, "sweep", multi=False)

        strategy_type = st.sidebar.selectbox(
            "Strategy Type:", STRATEGY_NAMES, key="sweep_type",
        )
        config = SWEEP_SIDEBAR_REGISTRY[strategy_type](ticker, data_source)

        from_date = sidebar_from_date("sweep")
        config["from_date"] = from_date

        return config

    def run_sweep(
        self, df: pd.DataFrame, config: Dict
    ) -> Tuple[List[Tuple[int, str, Dict]], List[int]]:
        results: List[Tuple[int, str, Dict]] = []
        skipped: List[int] = []

        for length in config["sweep_lengths"]:
            if should_skip_sweep_length(config["strategy_type"], config, length):
                skipped.append(length)
                continue

            strategy = build_from_sweep_config(config["strategy_type"], config, length)
            label = sweep_label(config["strategy_type"], config, length)
            core_config = {**config, "strategy": strategy}
            core = self._compute_ticker_core(config["ticker"], df, core_config)
            results.append((length, label, core))

        return results, skipped

    def run_computation(self, ticker: str, df: pd.DataFrame, config: Dict) -> AnalysisResult:
        pass  # Not used — computation via run_sweep()

    def render_results(self, result: AnalysisResult) -> None:
        pass  # Not used — rendering via render_sweep_results()

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render_variant_expander(
        self, length: int, label: str, core: Dict, ticker: str
    ) -> None:
        with st.expander(f"{label}", expanded=False):
            perf = core["performance"]
            trades = core["trades"]

            st.markdown("**Performance Summary**")
            render_performance_summary(perf, core["strat_max_drawdown"])

            st.divider()

            st.markdown("**Trade Log**")
            if trades:
                bh_eq = core["bh_equity"]
                sorted_trades = sorted(trades, key=lambda x: x.entry_date, reverse=True)
                trade_rows = []
                for t in sorted_trades:
                    eq_close = t.equity_at_close
                    bh_close = (
                        float(bh_eq.asof(pd.Timestamp(t.exit_date)))
                        if t.exit_date is not None and bh_eq is not None
                        else None
                    )
                    trade_rows.append({
                        "Entry Date":      t.entry_date.strftime(DATE_FORMAT_DISPLAY),
                        "Entry Price":     fmt_price(t.entry_price),
                        "Exit Date":       t.exit_date.strftime(DATE_FORMAT_DISPLAY) if t.exit_date else "—",
                        "Exit Price":      fmt_price(t.exit_price) if t.exit_price else "—",
                        "Return %":        fmt_pct(t.return_pct) if t.return_pct is not None else "—",
                        "Equity at Close": fmt_equity(eq_close) if eq_close is not None else "—",
                        "B&H at Close":    fmt_equity(bh_close) if bh_close is not None else "—",
                        "Holding":         t.holding_days,
                        "Status":          t.status,
                    })

                trade_df = pd.DataFrame(trade_rows)
                returns_numeric = [t.return_pct for t in sorted_trades]
                statuses = [t.status for t in sorted_trades]

                def _trade_row_style(row: pd.Series):
                    if statuses[row.name] == "open":
                        return [COLOR_ACTIVE] * len(row)
                    return [style_positive_negative(returns_numeric[row.name])] * len(row)

                styled_trades = trade_df.style.apply(_trade_row_style, axis=1)
                st.dataframe(styled_trades, use_container_width=True, hide_index=True,
                             height=38 + min(len(trade_df), 15) * 35)
            else:
                st.info("No trades generated.")

            st.divider()

            st.markdown("**Return Distribution**")
            closed = [t for t in trades if t.status == "closed" and t.return_pct is not None]
            render_distribution([t.return_pct for t in closed], "Return", RETURN_BUCKETS, bucket_header="Return buckets")

            st.divider()

            winners = [t for t in trades if t.status == "closed" and t.return_pct is not None and t.return_pct > 0]
            st.markdown("**MAE of Winning Trades**")
            render_distribution(
                [t.mae_pct for t in winners if t.mae_pct is not None], "MAE %", NONNEG_BUCKETS
            )

            st.divider()

            st.markdown("**MFE of Winning Trades**")
            render_distribution(
                [t.mfe_pct for t in winners if t.mfe_pct is not None], "MFE %", NONNEG_BUCKETS
            )

            st.divider()

            strat_equity = core["strat_equity"]
            bh_equity = core["bh_equity"]
            render_monthly_returns_tables(strat_equity, bh_equity, ticker, trades)

            st.divider()

            render_deterioration_section(trades, strat_equity, ticker, key_suffix=f"sweep_{length}")

    def render_sweep_results(
        self,
        sweep_results: List[Tuple[int, str, Dict]],
        config: Dict,
        skipped: List[int],
    ) -> None:
        ticker = config["ticker"]
        st.subheader(f"📊 Parameter Sweep — {ticker}")
        st.caption(f"Ngày thống kê: {datetime.now().strftime(DATE_FORMAT_DISPLAY)}")

        if skipped:
            st.warning(f"Skipped {len(skipped)} length(s) where fast ≥ slow: {skipped}")

        if not sweep_results:
            st.warning("No valid parameter combinations to display.")
            return

        # ----- 1. Summary Comparison Table -----
        st.subheader("Summary Comparison")
        rows = []
        for length, label, core in sweep_results:
            perf = core["performance"]
            bh_return = core["bh_total_return"]
            strat_return = perf.total_return
            closed_returns = [
                t.return_pct for t in core["trades"]
                if t.status == "closed" and t.return_pct is not None
            ]
            rows.append({
                "MA Length":      length,
                "Return %":       round(strat_return, 2),
                "B&H %":          round(bh_return, 2),
                "Capture":        round(strat_return / bh_return, 2) if bh_return and bh_return > 0 else None,
                "Win Rate %":     round(perf.win_rate, 2),
                "Trades":         perf.closed_trades,
                "Wins":           perf.win_count,
                "Losses":         perf.loss_count,
                **compute_summary_percentiles(closed_returns),
                "Max DD %":       round(core["strat_max_drawdown"], 2),
                "Avg Hold Days":  int(round(perf.avg_holding_days)),
            })

        df_summary = pd.DataFrame(rows)
        PERCENTILE_COLS = [f"P{p} %" for p in SUMMARY_PERCENTILES]
        _fmt_pct_or_dash = lambda v: fmt_pct(v) if v is not None else "—"

        styled = (
            df_summary.style
            .applymap(style_capture, subset=["Capture"])
            .applymap(style_positive_negative, subset=PERCENTILE_COLS)
            .format(
                {
                    "Return %":    fmt_pct,
                    "B&H %":       fmt_pct,
                    "Capture":     fmt_capture,
                    "Win Rate %":  fmt_pct,
                    **{f"P{p} %": _fmt_pct_or_dash for p in SUMMARY_PERCENTILES},
                    "Max DD %":    fmt_pct,
                },
                na_rep="—",
            )
        )
        st.dataframe(styled, hide_index=True, use_container_width=True,
                     height=38 + min(len(df_summary), 30) * 35)

        st.divider()

        # ----- 2. Key Metrics Charts -----
        st.subheader("📊 Key Metrics Comparison")

        lengths_str = [str(l) for l, _, _ in sweep_results]
        closed_returns_by_len = [
            [t.return_pct for t in core["trades"] if t.status == "closed" and t.return_pct is not None]
            for _, _, core in sweep_results
        ]

        plot_chart(build_return_chart(
            lengths_str,
            [core["performance"].total_return for _, _, core in sweep_results],
            sweep_results[0][2]["bh_total_return"],
        ))
        plot_chart(build_drawdown_chart(
            lengths_str,
            [core["strat_max_drawdown"] for _, _, core in sweep_results],
        ))
        plot_chart(build_trade_count_chart(
            lengths_str,
            [core["performance"].win_count  for _, _, core in sweep_results],
            [core["performance"].loss_count for _, _, core in sweep_results],
        ))
        plot_chart(build_win_rate_chart(
            lengths_str,
            [core["performance"].win_rate for _, _, core in sweep_results],
        ))

        bw_log = st.checkbox("Log returns", value=False, key="sweep_bw_log")
        plot_chart(build_boxplot_chart(sweep_results, closed_returns_by_len, bw_log))

        st.divider()

        # ----- 3. Per-Variant Detail (collapsed expanders) -----
        st.subheader("🔍 Per-Variant Detail")
        for length, label, core in sweep_results:
            self._render_variant_expander(length, label, core, ticker)
