"""Parameter Sweep pack — compare strategy parameters on a single ticker."""
from datetime import datetime
from typing import Any, Dict, List, Tuple

import pandas as pd
import streamlit as st

from src.shared.base import BaseSweepPack, PackResult
from src.shared.constants import (
    DATE_FORMAT_DISPLAY,
    DISTRIBUTION_PERCENTILES,
    NONNEG_BUCKETS,
    RETURN_BUCKETS,
    SUMMARY_PERCENTILES,
)
from src.shared.fmt import fmt_capture, fmt_pct
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
from src.app.strategy_compute import compute_strategy
from src.app.packs._renderers import (
    render_strategy_health_section,
    render_distribution,
    render_monthly_returns_tables,
    render_performance_summary,
)
from src.app.widgets.position_widget import render_trade_log
from src.app.strategy_sidebar_factories import (
    SWEEP_SIDEBAR_REGISTRY,
    build_from_sweep_config,
    should_skip_sweep_length,
    sweep_label,
)
from src.app.ui import plot_chart, sidebar_data_source, sidebar_from_date, sidebar_ticker_input


class ParameterSweepPack(BaseSweepPack):
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
            core = compute_strategy(df, strategy, strategy.name, config.get("from_date"))
            results.append((length, label, core))

        return results, skipped

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render_variant_expander(
        self, length: int, label: str, core: Dict, ticker: str
    ) -> None:
        with st.expander(f"{label}", expanded=False):
            perf = core["performance"]
            trades = core["trades"]

            render_performance_summary(perf, core["strat_max_drawdown"])

            st.divider()

            render_trade_log(trades, core["bh_equity"])

            st.divider()

            st.markdown("**Return Distribution**")
            closed = [t for t in trades if t.status == "closed" and t.return_pct is not None]
            render_distribution([t.return_pct for t in closed], "Return", RETURN_BUCKETS, DISTRIBUTION_PERCENTILES, bucket_header="Return buckets")

            st.divider()

            winners = [t for t in trades if t.status == "closed" and t.return_pct is not None and t.return_pct > 0]
            st.markdown("**MAE of Winning Trades**")
            render_distribution(
                [t.mae_pct for t in winners if t.mae_pct is not None], "MAE %", NONNEG_BUCKETS, DISTRIBUTION_PERCENTILES
            )

            st.divider()

            st.markdown("**MFE of Winning Trades**")
            render_distribution(
                [t.mfe_pct for t in winners if t.mfe_pct is not None], "MFE %", NONNEG_BUCKETS, DISTRIBUTION_PERCENTILES
            )

            st.divider()

            strat_equity = core["strat_equity"]
            bh_equity = core["bh_equity"]
            render_monthly_returns_tables(strat_equity, bh_equity, ticker, trades)

            st.divider()

            render_strategy_health_section(trades, strat_equity, ticker, key_suffix=f"sweep_{length}")

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
