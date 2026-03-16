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
    YFINANCE_PRESETS,
    fmt_capture,
    fmt_equity,
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


# ---------------------------------------------------------------------------
# Shared sidebar — single source of truth for strategy parameters
# ---------------------------------------------------------------------------

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

    if data_source == "vnstock":
        group_choice = st.sidebar.selectbox(
            "Symbol Group:",
            VNSTOCK_GROUPS,
            key=f"{key_prefix}_vnstock_group",
        )
    else:
        group_choice = st.sidebar.selectbox(
            "Symbol Group:",
            YFINANCE_GROUPS,
            key=f"{key_prefix}_yfinance_group",
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
        "vnstock_group": group_choice,
    }


class StrategyBacktestPack(AnalysisPack):
    @property
    def pack_name(self) -> str:
        return "Strategy Backtest"

    def render_sidebar(self) -> Dict[str, Any]:
        return render_strategy_sidebar(key_prefix="strat", header="Strategy Backtest")

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

        INITIAL_CAPITAL = 1000.0
        strat_equity = build_equity_curve(price, buy_signals, sell_signals, INITIAL_CAPITAL)
        bh_equity = price / float(price.iloc[0]) * INITIAL_CAPITAL

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
            fig = self._build_equity_chart(
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
    def _render_nonneg_distribution(values: list, metric_label: str, bar_color: str) -> None:
        """Generic distribution renderer for non-negative metrics (MFE, MAE)."""
        if len(values) < 2:
            st.info("Not enough closed trades to show distribution.")
            return

        percentiles = [5, 10, 25, 50, 75, 90, 95]
        pct_rows = []
        for p in percentiles:
            pct_rows.append({"Percentile": f"P{p}", metric_label: fmt_pct(np.percentile(values, p))})
        pct_rows.append({"Percentile": "Mean",    metric_label: fmt_pct(np.mean(values))})
        pct_rows.append({"Percentile": "Std Dev", metric_label: fmt_pct(np.std(values, ddof=1))})

        buckets = [
            ("0 → 5%",      0,   5),
            ("5 → 10%",     5,  10),
            ("10 → 20%",   10,  20),
            ("20 → 30%",   20,  30),
            ("30 → 50%",   30,  50),
            ("50 → 100%",  50, 100),
            ("> 100%",    100, float("inf")),
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
                f"Avg {metric_label}": fmt_pct(np.mean(subset)) if subset else "—",
            })

        col_stats, col_buckets = st.columns(2)
        with col_stats:
            st.markdown("**Percentile breakdown**")
            st.dataframe(pd.DataFrame(pct_rows), hide_index=True, use_container_width=True,
                         height=38 + len(pct_rows) * 35)
        with col_buckets:
            st.markdown("**Buckets**")
            st.dataframe(pd.DataFrame(bucket_rows), hide_index=True, use_container_width=True,
                         height=38 + len(bucket_rows) * 35)

        mean_v = float(np.mean(values))
        median_v = float(np.median(values))
        fig = go.Figure()
        fig.add_trace(go.Histogram(x=values, name=metric_label, marker_color=bar_color, xbins=dict(size=2)))
        fig.add_vline(x=mean_v, line_dash="dash", line_color="white",
                      annotation_text=f"Mean {mean_v:.1f}%", annotation_position="top right")
        fig.add_vline(x=median_v, line_dash="dot", line_color="yellow",
                      annotation_text=f"Median {median_v:.1f}%", annotation_position="top left")
        fig.update_layout(height=350, xaxis_title=f"{metric_label} (%)", yaxis_title="# Trades",
                          hovermode="x unified", showlegend=False, margin=dict(t=30))
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
            year_monthly_vals = []
            month_vals: Dict[str, Any] = {}
            for m_i, m_name in enumerate(MONTHS, start=1):
                mask = (monthly_ret.index.year == yr) & (monthly_ret.index.month == m_i)
                vals = monthly_ret[mask]
                if len(vals) > 0:
                    v = float(vals.iloc[0])
                    month_vals[m_name] = fmt_pct(v)
                    year_monthly_vals.append(v)
                else:
                    month_vals[m_name] = ""

            # Compound annual / YTD return
            if year_monthly_vals:
                compound = 1.0
                for v in year_monthly_vals:
                    compound *= (1 + v / 100)
                annual = fmt_pct((compound - 1) * 100)
            else:
                annual = ""

            row: Dict[str, Any] = {"Year": str(yr), "Annual": annual, **month_vals}

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
    def _build_trade_entry_month_stats_df(trades, value_attr: str = "return_pct") -> pd.DataFrame:
        """
        Group closed trades by entry month, compute percentile distribution of a trade attribute.
        Rows = months (Jan–Dec), columns = # Trades, P95 … P5.
        value_attr: Trade field to use — 'return_pct' or 'mfe_pct'.
        """
        MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                       "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        PERCENTILES = [95, 90, 80, 70, 60, 50, 40, 30, 20, 10, 5]

        closed = [t for t in trades if t.status == "closed" and getattr(t, value_attr) is not None]

        rows = []
        for m_i, m_name in enumerate(MONTH_NAMES, start=1):
            month_vals = [getattr(t, value_attr) for t in closed if t.entry_date.month == m_i]
            row: Dict[str, Any] = {"Month": m_name, "# Trades": len(month_vals)}
            if month_vals:
                for p in PERCENTILES:
                    row[f"P{p}"] = fmt_pct(float(np.percentile(month_vals, p)))
            else:
                for p in PERCENTILES:
                    row[f"P{p}"] = "—"
            rows.append(row)
        return pd.DataFrame(rows)

    @staticmethod
    def _render_monthly_returns_tables(
        strat_equity: pd.Series,
        bh_equity: pd.Series,
        ticker: str,
        trades: list = None,
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

        if trades:
            st.divider()
            st.subheader("📊 Monthly Statistics — Return by Trade Entry Month")
            st.caption("Percentile distribution of trade returns grouped by the month the position was opened.")
            entry_stats = StrategyBacktestPack._build_trade_entry_month_stats_df(trades, "return_pct")
            st.dataframe(
                StrategyBacktestPack._style_monthly_stats_df(entry_stats),
                hide_index=True,
                use_container_width=True,
                height=38 + 12 * 35,
            )

            st.subheader("📊 Monthly Statistics — MFE by Trade Entry Month")
            st.caption("Percentile distribution of Maximum Favorable Excursion grouped by the month the position was opened.")
            mfe_stats = StrategyBacktestPack._build_trade_entry_month_stats_df(trades, "mfe_pct")
            st.dataframe(
                StrategyBacktestPack._style_monthly_stats_df(mfe_stats),
                hide_index=True,
                use_container_width=True,
                height=38 + 12 * 35,
            )

    @staticmethod
    def _render_deterioration_section(trades, strat_equity: pd.Series, ticker: str) -> None:
        from src.strategy.analytics import Trade

        closed = [t for t in trades if t.status == "closed" and t.return_pct is not None and t.entry_date is not None]

        st.subheader("📉 Strategy Health Over Time")
        st.caption(
            "These views help identify whether strategy performance is deteriorating. "
            "Strong aggregate stats can mask recent weakness — check the most recent years and rolling windows."
        )

        # --- 1. Annual Trade Summary ---
        st.subheader("Annual Trade Summary")
        st.caption("Per-year trade statistics. Recent years at the top.")

        if len(closed) < 2:
            st.info("Not enough closed trades for annual breakdown.")
        else:
            from collections import defaultdict
            PERCENTILES = [90, 80, 70, 60, 50, 40, 30, 20, 10]

            # Group trades by year of entry, preserving entry order for compounding
            year_trades: dict = defaultdict(list)
            for t in sorted(closed, key=lambda x: x.entry_date):
                year_trades[t.entry_date.year].append(t.return_pct)

            annual_rows = []
            for yr in sorted(year_trades.keys(), reverse=True):
                rets = year_trades[yr]
                wins = [r for r in rets if r > 0]

                # Compound return: $1000 → trade sequentially through each closed trade that year
                capital = 1000.0
                for r in rets:
                    capital *= (1 + r / 100)
                total_return_pct = (capital / 1000.0 - 1) * 100

                losses = [r for r in rets if r <= 0]
                row: Dict[str, Any] = {
                    "Year": str(yr),
                    "Trades": len(rets),
                    "Total Return (%)": fmt_pct(total_return_pct),
                    "Win Rate": fmt_pct(len(wins) / len(rets) * 100),
                    "Avg. Win (%)": fmt_pct(float(np.mean(wins))) if wins else "—",
                    "Avg. Loss (%)": fmt_pct(float(np.mean(losses))) if losses else "—",
                }
                for p in PERCENTILES:
                    row[f"P{p}"] = fmt_pct(float(np.percentile(rets, p)))
                row["_total_return_num"] = total_return_pct
                annual_rows.append(row)

            ann_df = pd.DataFrame(annual_rows)
            display_df = ann_df.drop(columns=["_total_return_num"])
            num_total_return = ann_df["_total_return_num"].tolist()

            pct_cols = ["Total Return (%)", "Avg. Win (%)", "Avg. Loss (%)"] + [f"P{p}" for p in PERCENTILES]

            def _annual_cell_style(val):
                if not isinstance(val, str) or val == "":
                    return ""
                try:
                    numeric = float(val.replace(",", "").replace("%", ""))
                except ValueError:
                    return ""
                return style_positive_negative(numeric, threshold=0)

            styled_ann = display_df.style.applymap(_annual_cell_style, subset=pct_cols)
            st.dataframe(styled_ann, hide_index=True, use_container_width=True,
                         height=38 + len(display_df) * 35)

        st.divider()

        # --- 2. Rolling N-Trade Chart ---
        st.subheader("Rolling N-Trade Performance")
        st.caption("Rolling win rate and average return over the last N closed trades.")

        if len(closed) < 5:
            st.info("Not enough closed trades for rolling analysis.")
        else:
            n = st.slider("Rolling window (trades):", 5, 30, 10, key=f"rolling_n_{ticker}")
            sorted_closed = sorted(closed, key=lambda t: t.entry_date)
            dates = [t.entry_date for t in sorted_closed]
            rets = [t.return_pct for t in sorted_closed]
            wins_bin = [1 if r > 0 else 0 for r in rets]

            roll_wr, roll_avg, roll_avg_win, roll_avg_loss = [], [], [], []
            for i in range(len(sorted_closed)):
                window_start = max(0, i - n + 1)
                w_rets = rets[window_start: i + 1]
                w_wins = wins_bin[window_start: i + 1]
                roll_wr.append(sum(w_wins) / len(w_wins) * 100)
                roll_avg.append(float(np.mean(w_rets)))
                win_rets = [r for r in w_rets if r > 0]
                loss_rets = [r for r in w_rets if r <= 0]
                roll_avg_win.append(float(np.mean(win_rets)) if win_rets else None)
                roll_avg_loss.append(float(np.mean(loss_rets)) if loss_rets else None)

            fig_roll = go.Figure()
            fig_roll.add_trace(go.Scatter(
                x=dates, y=roll_wr, mode="lines", name="Rolling Win Rate (%)",
                line=dict(color="#4ADE80", width=2),
                hovertemplate="Win Rate: %{y:.1f}%<extra></extra>",
            ))
            fig_roll.add_hline(y=50, line_dash="dot", line_color="gray", line_width=1)
            fig_roll.update_layout(
                height=280, yaxis_title="Win Rate (%)",
                hovermode="x unified", margin=dict(t=20, b=20), showlegend=True,
            )
            try:
                st.plotly_chart(fig_roll, width="stretch")
            except TypeError:
                st.plotly_chart(fig_roll, use_container_width=True)

            fig_avg = go.Figure()
            fig_avg.add_trace(go.Scatter(
                x=dates, y=roll_avg, mode="lines", name="Rolling Avg Return (%)",
                line=dict(color="#FBBF24", width=2),
                hovertemplate="Avg Return: %{y:.2f}%<extra></extra>",
            ))
            fig_avg.add_hline(y=0, line_dash="dot", line_color="gray", line_width=1)
            fig_avg.update_layout(
                height=280, yaxis_title="Avg Return (%)",
                hovermode="x unified", margin=dict(t=20, b=20), showlegend=True,
            )
            try:
                st.plotly_chart(fig_avg, width="stretch")
            except TypeError:
                st.plotly_chart(fig_avg, use_container_width=True)

            wl_log = st.checkbox("Log returns", value=False, key=f"wl_log_{ticker}")

            def _to_log(v):
                return np.log1p(v / 100) * 100 if v is not None else None

            wl_avg_win  = [_to_log(v) for v in roll_avg_win]  if wl_log else roll_avg_win
            wl_avg_loss = [_to_log(v) for v in roll_avg_loss] if wl_log else roll_avg_loss

            fig_win_loss = go.Figure()
            fig_win_loss.add_trace(go.Scatter(
                x=dates, y=wl_avg_win, mode="lines", name="Rolling Avg. Win (%)",
                line=dict(color="#4ADE80", width=2),
                connectgaps=False,
                hovertemplate="Avg Win: %{y:.2f}%<extra></extra>",
            ))
            fig_win_loss.add_trace(go.Scatter(
                x=dates, y=wl_avg_loss, mode="lines", name="Rolling Avg. Loss (%)",
                line=dict(color="#F87171", width=2),
                connectgaps=False,
                hovertemplate="Avg Loss: %{y:.2f}%<extra></extra>",
            ))
            fig_win_loss.add_hline(y=0, line_dash="dot", line_color="gray", line_width=1)
            fig_win_loss.update_layout(
                height=280, yaxis_title="Log Return (%)" if wl_log else "Return (%)",
                hovermode="x unified", margin=dict(t=20, b=20), showlegend=True,
            )
            try:
                st.plotly_chart(fig_win_loss, width="stretch")
            except TypeError:
                st.plotly_chart(fig_win_loss, use_container_width=True)

        st.divider()

        # --- 3. Trade Return Scatter + Trend Line ---
        st.subheader("Trade Return Trend")
        st.caption("Each dot is a closed trade. The trend line shows whether returns are improving or declining over time.")

        if len(closed) < 3:
            st.info("Not enough closed trades for trend analysis.")
        else:
            sorted_closed = sorted(closed, key=lambda t: t.entry_date)
            dates = [t.entry_date for t in sorted_closed]
            rets = [t.return_pct for t in sorted_closed]

            scatter_log = st.checkbox("Log returns", value=False, key=f"scatter_log_{ticker}")

            def _log_ret(r):
                return np.log1p(r / 100) * 100

            plot_rets = [_log_ret(r) for r in rets] if scatter_log else rets

            # Numeric x for polyfit (days since first trade)
            first_date = dates[0]
            x_days = np.array([(d - first_date).days for d in dates], dtype=float)
            y = np.array(plot_rets, dtype=float)
            coeffs = np.polyfit(x_days, y, 1)
            trend_y = np.polyval(coeffs, x_days)

            # Slope per month (~30 days)
            slope_per_month = coeffs[0] * 30

            win_dates  = [d for d, r in zip(dates, plot_rets) if r > 0]
            win_rets   = [r for r in plot_rets if r > 0]
            loss_dates = [d for d, r in zip(dates, plot_rets) if r <= 0]
            loss_rets  = [r for r in plot_rets if r <= 0]

            # Hover text: entry date + return
            def _hover(d, r):
                return f"{d.strftime('%Y-%m-%d')}<br>Return: {r:+.2f}%"

            # Marker size scaled by abs(return), clamped 6–18
            def _sizes(ret_list):
                if not ret_list:
                    return []
                abs_r = [abs(r) for r in ret_list]
                lo, hi = min(abs_r), max(abs_r)
                span = hi - lo if hi > lo else 1
                return [6 + 12 * (a - lo) / span for a in abs_r]

            trend_color = "#F472B6" if slope_per_month < 0 else "#60A5FA"
            direction = "▲" if slope_per_month >= 0 else "▼"

            fig_scatter = go.Figure()

            # Zero reference band (subtle)
            fig_scatter.add_hrect(y0=-2, y1=2, fillcolor="rgba(255,255,255,0.03)",
                                  line_width=0, layer="below")
            fig_scatter.add_hline(y=0, line_color="rgba(255,255,255,0.25)", line_width=1)

            # Win dots
            if win_dates:
                fig_scatter.add_trace(go.Scatter(
                    x=win_dates, y=win_rets, mode="markers",
                    name="Win",
                    marker=dict(
                        color="rgba(74, 222, 128, 0.85)",
                        size=_sizes(win_rets),
                        line=dict(color="rgba(74,222,128,0.4)", width=1),
                        symbol="circle",
                    ),
                    text=[_hover(d, r) for d, r in zip(win_dates, win_rets)],
                    hovertemplate="%{text}<extra></extra>",
                ))

            # Loss dots
            if loss_dates:
                fig_scatter.add_trace(go.Scatter(
                    x=loss_dates, y=loss_rets, mode="markers",
                    name="Loss",
                    marker=dict(
                        color="rgba(248, 113, 113, 0.85)",
                        size=_sizes(loss_rets),
                        line=dict(color="rgba(248,113,113,0.4)", width=1),
                        symbol="circle",
                    ),
                    text=[_hover(d, r) for d, r in zip(loss_dates, loss_rets)],
                    hovertemplate="%{text}<extra></extra>",
                ))

            # Trend line with gradient-feel via slight glow (shadow trace)
            fig_scatter.add_trace(go.Scatter(
                x=dates, y=trend_y.tolist(), mode="lines",
                name="Trend",
                line=dict(color=trend_color, width=4),
                opacity=0.25,
                showlegend=False,
                hoverinfo="skip",
            ))
            fig_scatter.add_trace(go.Scatter(
                x=dates, y=trend_y.tolist(), mode="lines",
                name=f"Trend ({direction} {slope_per_month:+.2f}% / month)",
                line=dict(color=trend_color, width=2, dash="dot"),
                hovertemplate="Trend: %{y:.2f}%<extra></extra>",
            ))

            # Slope badge
            badge_color = "#60A5FA" if slope_per_month >= 0 else "#F472B6"
            fig_scatter.add_annotation(
                x=0.99, y=0.97, xref="paper", yref="paper",
                text=f"<b>{direction} {slope_per_month:+.2f}% / month</b>",
                showarrow=False,
                font=dict(size=14, color=badge_color),
                bgcolor="rgba(15,15,25,0.75)",
                bordercolor=badge_color,
                borderwidth=1.5,
                borderpad=6,
                xanchor="right",
            )

            fig_scatter.update_layout(
                height=480,
                yaxis_title="Log Return (%)" if scatter_log else "Return (%)",
                yaxis=dict(zeroline=False, gridcolor="rgba(255,255,255,0.06)"),
                xaxis=dict(gridcolor="rgba(255,255,255,0.06)"),
                hovermode="closest",
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0),
                margin=dict(t=50, b=30),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
            )
            try:
                st.plotly_chart(fig_scatter, width="stretch")
            except TypeError:
                st.plotly_chart(fig_scatter, use_container_width=True)

        st.divider()

        # --- 4. Rolling 12-Month Strategy Return ---
        st.subheader("Rolling 12-Month Strategy Return")
        st.caption(
            "Trailing 12-month return of the strategy equity curve. "
            "Sustained negative periods indicate recent underperformance."
        )

        if strat_equity is None or len(strat_equity) < 252:
            st.info("Not enough equity curve data for rolling 12-month return (need at least 252 days).")
        else:
            rolling_12m = strat_equity.pct_change(periods=252) * 100
            rolling_12m = rolling_12m.dropna()

            r12_log = st.checkbox("Log returns", value=False, key=f"r12_log_{ticker}")
            if r12_log:
                rolling_12m = np.log1p(rolling_12m / 100) * 100

            fig_r12 = go.Figure()

            # Shade positive/negative regions via filled area
            fig_r12.add_trace(go.Scatter(
                x=rolling_12m.index,
                y=rolling_12m.clip(lower=0),
                fill="tozeroy",
                mode="none",
                name="Positive",
                fillcolor="rgba(34, 197, 94, 0.25)",
            ))
            fig_r12.add_trace(go.Scatter(
                x=rolling_12m.index,
                y=rolling_12m.clip(upper=0),
                fill="tozeroy",
                mode="none",
                name="Negative",
                fillcolor="rgba(239, 68, 68, 0.25)",
            ))
            fig_r12.add_trace(go.Scatter(
                x=rolling_12m.index, y=rolling_12m,
                mode="lines", name="Rolling 12M Return",
                line=dict(color="#FFD700", width=2),
                hovertemplate="%{x|%Y-%m-%d}: %{y:.1f}%<extra></extra>",
            ))
            fig_r12.add_hline(y=0, line_color="gray", line_width=1)
            fig_r12.update_layout(
                height=400, yaxis_title="Trailing 12M Log Return (%)" if r12_log else "Trailing 12M Return (%)",
                hovermode="x unified", showlegend=True, margin=dict(t=30),
            )
            try:
                st.plotly_chart(fig_r12, width="stretch")
            except TypeError:
                st.plotly_chart(fig_r12, use_container_width=True)

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
            from datetime import datetime as _dt
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

            m9, m10, m11, m12, m13 = st.columns(5)
            m9.metric("Closed Trades", str(perf.closed_trades))
            m10.metric("Win Trades", str(perf.win_count))
            m11.metric("Loss Trades", str(perf.loss_count))
            m12.metric("Best Trade", fmt_pct(perf.best_trade_return))
            m13.metric("Worst Trade", fmt_pct(perf.worst_trade_return))

            st.divider()

            # 3. Strategy vs Buy & Hold
            st.subheader("📈 Strategy vs Buy & Hold")
            capture = perf.total_return / bh_total_return if bh_total_return and bh_total_return != 0 else None
            cmp_data = {
                "Metric":      ["Total Return (%)", "Max Drawdown (%)"],
                "Strategy":    [fmt_pct(perf.total_return), fmt_pct(strat_max_drawdown)],
                "Buy & Hold":  [fmt_pct(bh_total_return),   fmt_pct(bh_max_drawdown)],
                "Capture":     [fmt_capture(capture),        ""],
            }
            cmp_df = pd.DataFrame(cmp_data)

            def _style_capture_cell(val):
                if not isinstance(val, str) or val == "" or val == "—":
                    return ""
                try:
                    return COLOR_POSITIVE if float(val.replace("×", "")) > 1 else COLOR_NEGATIVE
                except ValueError:
                    return ""

            styled_cmp = cmp_df.style.applymap(_style_capture_cell, subset=["Capture"])
            st.dataframe(
                styled_cmp,
                hide_index=True,
                use_container_width=True,
                height=38 + 2 * 35,
            )

            st.divider()

            # 4. Trade Log (above chart, no expander)
            st.subheader("📋 Trade Log")
            if trades:
                strat_equity = result.data.get("strat_equity")
                bh_equity    = result.data.get("bh_equity")

                sorted_trades = sorted(trades, key=lambda x: x.entry_date, reverse=True)
                rows = []
                for t in sorted_trades:
                    if t.exit_date is not None and strat_equity is not None:
                        exit_ts = pd.Timestamp(t.exit_date)
                        # Normalise to $1 initial capital (curves built on $1,000)
                        eq_close  = float(strat_equity.asof(exit_ts)) / 1000
                        bh_close  = float(bh_equity.asof(exit_ts)) / 1000
                    else:
                        eq_close  = None
                        bh_close  = None

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

            # 5. MAE & MFE of winning trades
            winners = [t for t in trades if t.status == "closed" and t.return_pct is not None and t.return_pct > 0]
            st.subheader("📉 MAE of Winning Trades")
            st.caption("How far winning trades drew down before recovering. Use this to calibrate stop-loss levels: if your open trade exceeds the P90–P95 MAE of winners, it is statistically unlikely to recover.")
            mae_vals = [t.mae_pct for t in winners if t.mae_pct is not None]
            self._render_nonneg_distribution(mae_vals, "MAE %", "rgba(239, 68, 68, 0.7)")

            st.divider()

            st.subheader("📈 MFE of Winning Trades")
            st.caption("Peak unrealized gain reached during winning trades. Use this to calibrate take-profit levels.")
            mfe_vals = [t.mfe_pct for t in winners if t.mfe_pct is not None]
            self._render_nonneg_distribution(mfe_vals, "MFE %", "rgba(34, 197, 94, 0.7)")

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
            self._render_monthly_returns_tables(strat_equity, bh_equity, result.ticker, trades)

            st.divider()

            self._render_deterioration_section(trades, strat_equity, result.ticker)
