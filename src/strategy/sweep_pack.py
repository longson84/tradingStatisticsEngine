"""Parameter Sweep pack — compare MA lengths on a single ticker."""
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.base import AnalysisResult
from src.constants import (
    COLOR_POSITIVE,
    DATE_FORMAT_DISPLAY,
    INITIAL_CAPITAL,
    PLOTLY_NEGATIVE,
    PLOTLY_POSITIVE,
    SUMMARY_PERCENTILES,
    compute_summary_percentiles,
    fmt_capture,
    fmt_pct,
    style_capture,
    style_positive_negative,
)

from src.strategy.pack import StrategyBacktestPack
from src.strategy.renderers import (
    render_deterioration_section,
    render_monthly_returns_tables,
    render_nonneg_distribution,
    render_performance_summary,
    render_return_distribution,
)
from src.strategy.strategies import MACrossoverStrategy, PriceVsMAStrategy
from src.ui import plot_chart, sidebar_data_source, sidebar_from_date, sidebar_ticker_input


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
            ["Price vs MA", "MA Crossover"],
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

        else:  # MA Crossover
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

        from_date = sidebar_from_date("sweep")
        config["from_date"] = from_date

        return config

    def _build_strategy(self, config: Dict, length: int):
        """Build a strategy instance for one sweep length."""
        if config["strategy_type"] == "Price vs MA":
            return PriceVsMAStrategy(
                config["ma_type"], length, config["buy_lag"], config["sell_lag"]
            )
        else:
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

    def _make_label(self, config: Dict, length: int) -> str:
        """Build a short legend label for a sweep variant."""
        if config["strategy_type"] == "Price vs MA":
            return f"{config['ma_type']}({length})"
        else:
            dim = config["sweep_dimension"]
            if dim == "fast":
                return f"{config['fast_ma_type']}({length})×{config['slow_ma_type']}({config['fixed_length']})"
            else:
                return f"{config['fast_ma_type']}({config['fixed_length']})×{config['slow_ma_type']}({length})"

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
            st.warning(
                f"Skipped {len(skipped)} length(s) where fast ≥ slow: {skipped}"
            )

        if not sweep_results:
            st.warning("No valid parameter combinations to display.")
            return

        # ----- 1. Summary Comparison Table -----
        st.subheader("Summary Comparison")
        rows = []
        for length, label, core in sweep_results:
            perf = core["performance"]
            trades = core["trades"]
            bh_return = core["bh_total_return"]
            strat_return = perf.total_return

            closed_returns = [
                t.return_pct for t in trades
                if t.status == "closed" and t.return_pct is not None
            ]

            capture = round(strat_return / bh_return, 2) if bh_return and bh_return > 0 else None

            rows.append({
                "MA Length":     length,
                "Return %":     round(strat_return, 2),
                "B&H %":        round(bh_return, 2),
                "Capture":      capture,
                "Win Rate %":   round(perf.win_rate, 2),
                "Trades":       perf.closed_trades,
                "Wins":         perf.win_count,
                "Losses":       perf.loss_count,
                **compute_summary_percentiles(closed_returns),
                "Max DD %":     round(core["strat_max_drawdown"], 2),
                "Avg Hold Days": int(round(perf.avg_holding_days)),
            })

        df_summary = pd.DataFrame(rows)

        PERCENTILE_COLS = [f"P{p} %" for p in SUMMARY_PERCENTILES]

        def _style_percentile(val):
            try:
                return style_positive_negative(float(val))
            except (TypeError, ValueError):
                return ""

        _fmt_pct_or_dash = lambda v: fmt_pct(v) if v is not None else "—"
        pct_formatters = {f"P{p} %": _fmt_pct_or_dash for p in SUMMARY_PERCENTILES}

        styled = (
            df_summary.style
            .applymap(style_capture, subset=["Capture"])
            .applymap(_style_percentile, subset=PERCENTILE_COLS)
            .format(
                {
                    "Return %":     fmt_pct,
                    "B&H %":        fmt_pct,
                    "Capture":      fmt_capture,
                    "Win Rate %":   fmt_pct,
                    **pct_formatters,
                    "Max DD %":     fmt_pct,
                },
                na_rep="—",
            )
        )

        height = 38 + min(len(df_summary), 30) * 35
        st.dataframe(styled, hide_index=True, use_container_width=True, height=height)

        st.divider()

        # ----- 2. Key Metrics Charts -----
        st.subheader("📊 Key Metrics Comparison")

        lengths_str = [str(l) for l, _, _ in sweep_results]
        labels     = [label for _, label, _ in sweep_results]
        total_returns = [core["performance"].total_return for _, _, core in sweep_results]
        max_dds       = [core["strat_max_drawdown"] for _, _, core in sweep_results]
        bh_return_val = sweep_results[0][2]["bh_total_return"]

        closed_returns_by_len = []
        for _, _, core in sweep_results:
            trades = core["trades"]
            cr = [t.return_pct for t in trades if t.status == "closed" and t.return_pct is not None]
            closed_returns_by_len.append(cr)

        # --- Chart A: Total Returns ---
        fig_ret = go.Figure()
        fig_ret.add_trace(go.Bar(
            x=lengths_str, y=total_returns,
            name="Total Return %",
            marker_color="#FFD700",
            hovertemplate="%{x}: %{y:.2f}%<extra>Total Return</extra>",
        ))
        fig_ret.add_hline(
            y=bh_return_val, line_dash="dash", line_color="gray", line_width=2,
            annotation_text=f"B&H: {bh_return_val:.1f}%",
            annotation_position="top left",
        )
        fig_ret.update_layout(
            title="Total Return % by MA Length",
            xaxis_title="MA Length", yaxis_title="Return %",
            height=380, hovermode="x unified", showlegend=False,
        )
        plot_chart(fig_ret)

        # --- Chart B: Max Drawdown ---
        fig_dd = go.Figure()
        fig_dd.add_trace(go.Bar(
            x=lengths_str, y=max_dds,
            name="Max Drawdown %",
            marker_color="#FF6B6B",
            hovertemplate="%{x}: %{y:.2f}%<extra>Max DD</extra>",
        ))
        fig_dd.update_layout(
            title="Max Drawdown % by MA Length",
            xaxis_title="MA Length", yaxis_title="Drawdown %",
            height=380, hovermode="x unified", showlegend=False,
        )
        plot_chart(fig_dd)

        # --- Chart C: Trade Count (wins up / losses down) ---
        win_counts  = [core["performance"].win_count  for _, _, core in sweep_results]
        loss_counts = [core["performance"].loss_count for _, _, core in sweep_results]
        total_counts = [w + l for w, l in zip(win_counts, loss_counts)]

        fig_trades = go.Figure()
        fig_trades.add_trace(go.Bar(
            x=lengths_str, y=win_counts,
            name="Win Trades",
            marker_color=PLOTLY_POSITIVE,
            hovertemplate="%{x}: %{y} wins<extra></extra>",
        ))
        fig_trades.add_trace(go.Bar(
            x=lengths_str, y=[-l for l in loss_counts],
            name="Loss Trades",
            marker_color=PLOTLY_NEGATIVE,
            hovertemplate="%{x}: %{customdata} losses<extra></extra>",
            customdata=loss_counts,
        ))
        # Total label above each bar
        for x_val, w, total in zip(lengths_str, win_counts, total_counts):
            fig_trades.add_annotation(
                x=x_val, y=w,
                text=str(total),
                showarrow=False,
                yshift=10,
                font=dict(size=11, color="white"),
            )
        fig_trades.update_layout(
            title="Trade Count by MA Length",
            xaxis_title="MA Length", yaxis_title="# Trades",
            barmode="relative",
            height=380, hovermode="x unified",
        )
        plot_chart(fig_trades)

        # --- Chart D: Win Rate ---
        win_rates = [core["performance"].win_rate for _, _, core in sweep_results]

        fig_wr = go.Figure()
        fig_wr.add_trace(go.Bar(
            x=lengths_str, y=win_rates,
            marker_color=[PLOTLY_POSITIVE if w >= 50 else PLOTLY_NEGATIVE for w in win_rates],
            hovertemplate="%{x}: %{y:.1f}%<extra>Win Rate</extra>",
        ))
        fig_wr.add_hline(y=50, line_dash="dash", line_color="gray", line_width=1,
                         annotation_text="50%", annotation_position="top left")
        fig_wr.update_layout(
            title="Win Rate % by MA Length",
            xaxis_title="MA Length", yaxis_title="Win Rate %",
            height=380, hovermode="x unified", showlegend=False,
        )
        plot_chart(fig_wr)

        # --- Chart E: Trade Return Distribution by MA Length (box plot) ---
        bw_log = st.checkbox("Log returns", value=False, key="sweep_bw_log")

        def _to_log(v):
            return np.log1p(v / 100) * 100 if v is not None else None

        fig_bw = go.Figure()
        for i, (length, label, core) in enumerate(sweep_results):
            cr = closed_returns_by_len[i]
            if not cr:
                continue

            p10 = float(np.percentile(cr, 10))
            p30 = float(np.percentile(cr, 30))
            p50 = float(np.percentile(cr, 50))
            p70 = float(np.percentile(cr, 70))
            p90 = float(np.percentile(cr, 90))

            if bw_log:
                p10, p30, p50, p70, p90 = [_to_log(v) for v in (p10, p30, p50, p70, p90)]

            # Box: P30–P70 body, P10–P90 whiskers
            fig_bw.add_trace(go.Box(
                x=[str(length)],
                lowerfence=[p10], q1=[p30], median=[p50], q3=[p70], upperfence=[p90],
                name=str(length),
                marker_color="#4ECDC4",
                fillcolor="rgba(78, 205, 196, 0.3)",
                line=dict(color="#4ECDC4"),
                whiskerwidth=0.5,
                showlegend=False,
                hoverinfo="y",
            ))

        fig_bw.add_hline(y=0, line_color="gray", line_width=1)
        fig_bw.update_layout(
            title="Trade Return Distribution by MA Length (P30–P70 box, P10–P90 whiskers)",
            xaxis_title="MA Length",
            yaxis_title="Log Return %" if bw_log else "Return %",
            height=480, hovermode="x unified", showlegend=True,
        )
        plot_chart(fig_bw)

        st.divider()

        # ----- 4. Per-Variant Detail (collapsed expanders) -----
        st.subheader("🔍 Per-Variant Detail")
        for length, label, core in sweep_results:
            with st.expander(f"{label}", expanded=False):
                perf = core["performance"]
                trades = core["trades"]

                # Performance summary metrics
                st.markdown("**Performance Summary**")
                render_performance_summary(perf, core["strat_max_drawdown"])

                st.divider()

                # Trade log
                st.markdown("**Trade Log**")
                if trades:
                    from src.constants import COLOR_ACTIVE, fmt_price, fmt_equity
                    bh_eq = core["bh_equity"]
                    sorted_trades = sorted(trades, key=lambda x: x.entry_date, reverse=True)
                    trade_rows = []
                    for t in sorted_trades:
                        eq_close = t.equity_at_close
                        if t.exit_date is not None and bh_eq is not None:
                            bh_close = float(bh_eq.asof(pd.Timestamp(t.exit_date)))
                        else:
                            bh_close = None

                        trade_rows.append({
                            "Entry Date": t.entry_date.strftime(DATE_FORMAT_DISPLAY),
                            "Entry Price": fmt_price(t.entry_price),
                            "Exit Date": t.exit_date.strftime(DATE_FORMAT_DISPLAY) if t.exit_date else "—",
                            "Exit Price": fmt_price(t.exit_price) if t.exit_price else "—",
                            "Return %": fmt_pct(t.return_pct) if t.return_pct is not None else "—",
                            "Equity at Close": fmt_equity(eq_close) if eq_close is not None else "—",
                            "B&H at Close": fmt_equity(bh_close) if bh_close is not None else "—",
                            "Holding": t.holding_days,
                            "Status": t.status,
                        })
                    trade_df = pd.DataFrame(trade_rows)

                    returns_numeric = [t.return_pct for t in sorted_trades]
                    statuses = [t.status for t in sorted_trades]

                    def _trade_row_style(row: pd.Series):
                        if statuses[row.name] == "open":
                            return [COLOR_ACTIVE] * len(row)
                        return [style_positive_negative(returns_numeric[row.name])] * len(row)

                    styled_trades = trade_df.style.apply(_trade_row_style, axis=1)
                    n_rows = len(trade_df)
                    t_height = 38 + min(n_rows, 15) * 35
                    st.dataframe(styled_trades, use_container_width=True, hide_index=True, height=t_height)
                else:
                    st.info("No trades generated.")

                st.divider()

                # Return distribution
                st.markdown("**Return Distribution**")
                render_return_distribution(trades)

                st.divider()

                # MAE & MFE
                winners = [t for t in trades if t.status == "closed" and t.return_pct is not None and t.return_pct > 0]
                st.markdown("**MAE of Winning Trades**")
                mae_vals = [t.mae_pct for t in winners if t.mae_pct is not None]
                render_nonneg_distribution(mae_vals, "MAE %", "rgba(239, 68, 68, 0.7)")

                st.divider()

                st.markdown("**MFE of Winning Trades**")
                mfe_vals = [t.mfe_pct for t in winners if t.mfe_pct is not None]
                render_nonneg_distribution(mfe_vals, "MFE %", "rgba(34, 197, 94, 0.7)")

                st.divider()

                # Monthly returns
                strat_equity = core["strat_equity"]
                bh_equity = core["bh_equity"]
                render_monthly_returns_tables(strat_equity, bh_equity, ticker, trades)

                st.divider()

                # Deterioration
                render_deterioration_section(trades, strat_equity, ticker, key_suffix=f"sweep_{length}")
