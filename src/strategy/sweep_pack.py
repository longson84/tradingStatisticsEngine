"""Parameter Sweep pack — compare MA lengths on a single ticker."""
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.base import AnalysisResult
from src.constants import (
    COLOR_ACTIVE,
    DATE_FORMAT_DISPLAY,
    NONNEG_BUCKETS,
    RETURN_BUCKETS,
    SUMMARY_PERCENTILES,
)
from src.fmt import fmt_capture, fmt_equity, fmt_pct, fmt_price
from src.styling import style_capture, style_positive_negative
from src.strategy.utils import compute_summary_percentiles

from src.strategy.pack import StrategyBacktestPack
from src.strategy.renderers import (
    render_deterioration_section,
    render_distribution,
    render_monthly_returns_tables,
    render_performance_summary,
)
from src.strategy.strategies import BollingerBandStrategy, DonchianBreakoutStrategy, MACrossoverStrategy, PriceVsMAStrategy
from src.strategy.sweep_charts import (
    build_boxplot_chart,
    build_drawdown_chart,
    build_return_chart,
    build_trade_count_chart,
    build_win_rate_chart,
)
from src.ui import plot_chart, sidebar_data_source, sidebar_from_date, sidebar_ticker_input


def _style_percentile(val) -> str:
    try:
        return style_positive_negative(float(val))
    except (TypeError, ValueError):
        return ""


class ParameterSweepPack(StrategyBacktestPack):
    @property
    def pack_name(self) -> str:
        return "Parameter Sweep"

    def render_sidebar(self) -> Dict[str, Any]:
        st.sidebar.header("Parameter Sweep")

        data_source = sidebar_data_source("sweep")
        ticker = sidebar_ticker_input(data_source, "sweep", multi=False)

        strategy_type = st.sidebar.selectbox(
            "Strategy Type:",
            ["Price vs MA", "MA Crossover", "Donchian Breakout", "Bollinger Bands"],
            key="sweep_type",
        )

        if strategy_type == "Price vs MA":
            ma_type = st.sidebar.selectbox("MA Type:", ["SMA", "EMA", "WMA"], key="sweep_pma_type")
            col1, col2 = st.sidebar.columns(2)
            buy_lag = col1.number_input("Buy Lag (days):", min_value=0, value=0, step=1, key="sweep_pma_buy_lag")
            sell_lag = col2.number_input("Sell Lag (days):", min_value=0, value=2, step=1, key="sweep_pma_sell_lag")

            st.sidebar.markdown("**MA Length Sweep Range**")
            c1, c2, c3 = st.sidebar.columns(3)
            sweep_min = c1.number_input("Min", min_value=2, value=20, step=5, key="sweep_pma_min")
            sweep_max = c2.number_input("Max", min_value=2, value=200, step=5, key="sweep_pma_max")
            sweep_step = c3.number_input("Step", min_value=1, value=10, step=1, key="sweep_pma_step")

            sweep_lengths = list(range(int(sweep_min), int(sweep_max) + 1, int(sweep_step)))

            config = {
                "ticker": ticker,
                "data_source": data_source,
                "vnstock_source": "KBS",
                "strategy_type": strategy_type,
                "ma_type": ma_type,
                "buy_lag": int(buy_lag),
                "sell_lag": int(sell_lag),
                "sweep_lengths": sweep_lengths,
            }

        elif strategy_type == "MA Crossover":
            sweep_dim = st.sidebar.radio(
                "Sweep:", ["Fast Length", "Slow Length"],
                key="sweep_mac_dim", horizontal=True,
            )

            col1, col2 = st.sidebar.columns(2)
            fast_ma_type = col1.selectbox("Fast MA Type:", ["EMA", "SMA", "WMA"], key="sweep_mac_fast_type")
            slow_ma_type = col2.selectbox("Slow MA Type:", ["SMA", "EMA", "WMA"], key="sweep_mac_slow_type")

            col3, col4 = st.sidebar.columns(2)
            buy_lag = col3.number_input("Buy Lag:", min_value=0, value=1, step=1, key="sweep_mac_buy_lag")
            sell_lag = col4.number_input("Sell Lag:", min_value=0, value=1, step=1, key="sweep_mac_sell_lag")

            if sweep_dim == "Fast Length":
                st.sidebar.markdown("**Fast Length Sweep Range**")
                c1, c2, c3 = st.sidebar.columns(3)
                sweep_min = c1.number_input("Min", min_value=2, value=10, step=5, key="sweep_mac_fast_min")
                sweep_max = c2.number_input("Max", min_value=2, value=100, step=5, key="sweep_mac_fast_max")
                sweep_step = c3.number_input("Step", min_value=1, value=10, step=1, key="sweep_mac_fast_step")
                fixed_length = st.sidebar.number_input(
                    "Fixed Slow Length:", min_value=2, value=200, step=10, key="sweep_mac_slow_fixed"
                )
            else:
                st.sidebar.markdown("**Slow Length Sweep Range**")
                c1, c2, c3 = st.sidebar.columns(3)
                sweep_min = c1.number_input("Min", min_value=2, value=100, step=10, key="sweep_mac_slow_min")
                sweep_max = c2.number_input("Max", min_value=2, value=300, step=10, key="sweep_mac_slow_max")
                sweep_step = c3.number_input("Step", min_value=1, value=20, step=1, key="sweep_mac_slow_step")
                fixed_length = st.sidebar.number_input(
                    "Fixed Fast Length:", min_value=2, value=50, step=10, key="sweep_mac_fast_fixed"
                )

            sweep_lengths = list(range(int(sweep_min), int(sweep_max) + 1, int(sweep_step)))

            config = {
                "ticker": ticker,
                "data_source": data_source,
                "vnstock_source": "KBS",
                "strategy_type": strategy_type,
                "fast_ma_type": fast_ma_type,
                "slow_ma_type": slow_ma_type,
                "sweep_dimension": "fast" if sweep_dim == "Fast Length" else "slow",
                "fixed_length": int(fixed_length),
                "buy_lag": int(buy_lag),
                "sell_lag": int(sell_lag),
                "sweep_lengths": sweep_lengths,
            }

        elif strategy_type == "Donchian Breakout":
            sweep_dim = st.sidebar.radio(
                "Sweep:", ["Entry Length", "Exit Length"],
                key="sweep_don_dim", horizontal=True,
            )

            st.sidebar.markdown(f"**{sweep_dim} Sweep Range**")
            c1, c2, c3 = st.sidebar.columns(3)
            sweep_min = c1.number_input("Min", min_value=2, value=10, step=5, key="sweep_don_min")
            sweep_max = c2.number_input("Max", min_value=2, value=50, step=5, key="sweep_don_max")
            sweep_step = c3.number_input("Step", min_value=1, value=5, step=1, key="sweep_don_step")

            fixed_label = "Fixed Exit Length:" if sweep_dim == "Entry Length" else "Fixed Entry Length:"
            fixed_default = 10 if sweep_dim == "Entry Length" else 20
            fixed_length = st.sidebar.number_input(
                fixed_label, min_value=2, value=fixed_default, step=5, key="sweep_don_fixed"
            )

            sweep_lengths = list(range(int(sweep_min), int(sweep_max) + 1, int(sweep_step)))

            config = {
                "ticker": ticker,
                "data_source": data_source,
                "vnstock_source": "KBS",
                "strategy_type": strategy_type,
                "sweep_dimension": "entry" if sweep_dim == "Entry Length" else "exit",
                "fixed_length": int(fixed_length),
                "sweep_lengths": sweep_lengths,
            }

        else:  # Bollinger Bands
            sweep_dim = st.sidebar.radio(
                "Sweep:", ["Period", "Std Dev"],
                key="sweep_bb_dim", horizontal=True,
            )

            if sweep_dim == "Period":
                st.sidebar.markdown("**Period Sweep Range**")
                c1, c2, c3 = st.sidebar.columns(3)
                sweep_min = c1.number_input("Min", min_value=5, value=10, step=5, key="sweep_bb_period_min")
                sweep_max = c2.number_input("Max", min_value=5, value=40, step=5, key="sweep_bb_period_max")
                sweep_step = c3.number_input("Step", min_value=1, value=5, step=1, key="sweep_bb_period_step")
                fixed_std = st.sidebar.number_input(
                    "Fixed Std Dev:", min_value=0.5, value=2.0, step=0.25, format="%.2f", key="sweep_bb_std_fixed"
                )
                sweep_lengths = list(range(int(sweep_min), int(sweep_max) + 1, int(sweep_step)))
            else:
                st.sidebar.markdown("**Std Dev Sweep Range**")
                c1, c2, c3 = st.sidebar.columns(3)
                sweep_min = c1.number_input("Min", min_value=0.5, value=1.0, step=0.25, format="%.2f", key="sweep_bb_std_min")
                sweep_max = c2.number_input("Max", min_value=0.5, value=3.0, step=0.25, format="%.2f", key="sweep_bb_std_max")
                sweep_step = c3.number_input("Step", min_value=0.25, value=0.25, step=0.25, format="%.2f", key="sweep_bb_std_step")
                fixed_period = st.sidebar.number_input(
                    "Fixed Period:", min_value=5, value=20, step=1, key="sweep_bb_period_fixed"
                )
                sweep_lengths = list(np.arange(float(sweep_min), float(sweep_max) + float(sweep_step) / 2, float(sweep_step)))

            config = {
                "ticker": ticker,
                "data_source": data_source,
                "vnstock_source": "KBS",
                "strategy_type": strategy_type,
                "sweep_dimension": "period" if sweep_dim == "Period" else "std_dev",
                "fixed_value": float(fixed_std) if sweep_dim == "Period" else int(fixed_period),
                "sweep_lengths": sweep_lengths,
            }

        from_date = sidebar_from_date("sweep")
        config["from_date"] = from_date

        return config

    def _build_strategy(self, config: Dict, length: int):
        """Build a strategy instance for one sweep length."""
        if config["strategy_type"] == "Price vs MA":
            return PriceVsMAStrategy(
                config["ma_type"], length, config["buy_lag"], config["sell_lag"]
            )
        elif config["strategy_type"] == "MA Crossover":
            dim = config["sweep_dimension"]
            if dim == "fast":
                fast_len, slow_len = length, config["fixed_length"]
            else:
                fast_len, slow_len = config["fixed_length"], length
            return MACrossoverStrategy(
                config["fast_ma_type"], fast_len,
                config["slow_ma_type"], slow_len,
                config["buy_lag"], config["sell_lag"],
            )
        elif config["strategy_type"] == "Donchian Breakout":
            dim = config["sweep_dimension"]
            if dim == "entry":
                return DonchianBreakoutStrategy(length, config["fixed_length"])
            else:
                return DonchianBreakoutStrategy(config["fixed_length"], length)
        else:  # Bollinger Bands
            dim = config["sweep_dimension"]
            if dim == "period":
                return BollingerBandStrategy(int(length), config["fixed_value"])
            else:
                return BollingerBandStrategy(config["fixed_value"], float(length))

    def _make_label(self, config: Dict, length: int) -> str:
        """Build a short legend label for a sweep variant."""
        if config["strategy_type"] == "Price vs MA":
            return f"{config['ma_type']}({length})"
        elif config["strategy_type"] == "MA Crossover":
            dim = config["sweep_dimension"]
            if dim == "fast":
                return f"{config['fast_ma_type']}({length})×{config['slow_ma_type']}({config['fixed_length']})"
            else:
                return f"{config['fast_ma_type']}({config['fixed_length']})×{config['slow_ma_type']}({length})"
        elif config["strategy_type"] == "Donchian Breakout":
            dim = config["sweep_dimension"]
            if dim == "entry":
                return f"Donchian({length}/{config['fixed_length']})"
            else:
                return f"Donchian({config['fixed_length']}/{length})"
        else:  # Bollinger Bands
            dim = config["sweep_dimension"]
            if dim == "period":
                return f"BB({length}, {config['fixed_value']}σ)"
            else:
                return f"BB({config['fixed_value']}, {length}σ)"

    def run_sweep(
        self, df: pd.DataFrame, config: Dict
    ) -> Tuple[List[Tuple[int, str, Dict]], List[int]]:
        """Run the sweep computation.

        Returns:
            (results, skipped) where results is a list of (length, label, core_dict)
            and skipped is the list of lengths that were filtered out.
        """
        results: List[Tuple[int, str, Dict]] = []
        skipped: List[int] = []

        for length in config["sweep_lengths"]:
            # For MACrossover, skip invalid combos where fast >= slow
            if config["strategy_type"] == "MA Crossover":
                dim = config["sweep_dimension"]
                if dim == "fast" and length >= config["fixed_length"]:
                    skipped.append(length)
                    continue
                if dim == "slow" and config["fixed_length"] >= length:
                    skipped.append(length)
                    continue

            strategy = self._build_strategy(config, length)
            label = self._make_label(config, length)
            core_config = {**config, "strategy": strategy}
            core = self._compute_ticker_core(config["ticker"], df, core_config)
            results.append((length, label, core))

        return results, skipped

    def render_results(self, result: AnalysisResult) -> None:
        pass  # Not used — rendering via render_sweep_results()

    def run_computation(self, ticker: str, df: pd.DataFrame, config: Dict) -> AnalysisResult:
        pass  # Not used — computation via run_sweep()

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render_variant_expander(
        self, length: int, label: str, core: Dict, ticker: str
    ) -> None:
        """Render the collapsed per-variant detail expander for one sweep result."""
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
            .applymap(_style_percentile, subset=PERCENTILE_COLS)
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
