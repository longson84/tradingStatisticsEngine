"""Streamlit rendering helpers for strategy backtest."""
from collections import defaultdict
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.constants import (
    COLOR_NEGATIVE,
    COLOR_POSITIVE,
    PLOTLY_NEGATIVE,
    PLOTLY_POSITIVE,
    fmt_pct,
    style_positive_negative,
)
from src.ui import plot_chart


# ---------------------------------------------------------------------------
# Return distribution
# ---------------------------------------------------------------------------

def render_return_distribution(trades) -> None:
    closed = [t for t in trades if t.status == "closed" and t.return_pct is not None]
    if len(closed) < 2:
        st.info("Not enough closed trades to show distribution.")
        return

    returns = [t.return_pct for t in closed]
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r <= 0]

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

    buckets = [
        ("< -20%",      float("-inf"), -20),
        ("-20 → -10%",         -20,   -10),
        ("-10 → -5%",          -10,    -5),
        ("-5 → 0%",             -5,     0),
        ("0 → 5%",               0,     5),
        ("5 → 10%",              5,    10),
        ("10 → 20%",            10,    20),
        ("> 20%",               20, float("inf")),
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

    fig = go.Figure()
    if wins:
        fig.add_trace(go.Histogram(x=wins, name="Win",
                                   marker_color="rgba(34, 197, 94, 0.7)", xbins=dict(size=2)))
    if losses:
        fig.add_trace(go.Histogram(x=losses, name="Loss",
                                   marker_color="rgba(239, 68, 68, 0.7)", xbins=dict(size=2)))

    mean_r = float(np.mean(returns))
    median_r = float(np.median(returns))
    fig.add_vline(x=mean_r, line_dash="dash", line_color="white",
                  annotation_text=f"Mean {mean_r:.1f}%", annotation_position="top right")
    fig.add_vline(x=median_r, line_dash="dot", line_color="yellow",
                  annotation_text=f"Median {median_r:.1f}%", annotation_position="top left")
    fig.add_vline(x=0, line_color="gray", line_width=1)
    fig.update_layout(barmode="overlay", height=350, xaxis_title="Return %",
                      yaxis_title="# Trades", hovermode="x unified",
                      showlegend=True, margin=dict(t=30))
    plot_chart(fig)


# ---------------------------------------------------------------------------
# Non-negative distribution (MAE / MFE)
# ---------------------------------------------------------------------------

def render_nonneg_distribution(values: list, metric_label: str, bar_color: str) -> None:
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
    plot_chart(fig)


# ---------------------------------------------------------------------------
# Retracement distribution
# ---------------------------------------------------------------------------

def render_retracement_distribution(trades) -> None:
    closed = [t for t in trades if t.status == "closed" and t.mfe_price and t.exit_price]
    if len(closed) < 2:
        st.info("Not enough closed trades to show retracement distribution.")
        return

    values = [(t.mfe_price - t.exit_price) / t.mfe_price * 100 for t in closed]

    percentiles = [5, 10, 25, 50, 75, 90, 95]
    pct_rows = []
    for p in percentiles:
        pct_rows.append({"Percentile": f"P{p}", "Retracement %": fmt_pct(np.percentile(values, p))})
    pct_rows.append({"Percentile": "Mean",    "Retracement %": fmt_pct(np.mean(values))})
    pct_rows.append({"Percentile": "Std Dev", "Retracement %": fmt_pct(np.std(values, ddof=1))})

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
        st.dataframe(pd.DataFrame(pct_rows), hide_index=True, use_container_width=True,
                     height=38 + len(pct_rows) * 35)
    with col_buckets:
        st.markdown("**Retracement buckets**")
        st.dataframe(pd.DataFrame(bucket_rows), hide_index=True, use_container_width=True,
                     height=38 + len(bucket_rows) * 35)

    mean_v = float(np.mean(values))
    median_v = float(np.median(values))
    fig = go.Figure()
    fig.add_trace(go.Histogram(x=values, name="Retracement",
                               marker_color="rgba(251, 191, 36, 0.7)", xbins=dict(size=2)))
    fig.add_vline(x=mean_v, line_dash="dash", line_color="white",
                  annotation_text=f"Mean {mean_v:.1f}%", annotation_position="top right")
    fig.add_vline(x=median_v, line_dash="dot", line_color="yellow",
                  annotation_text=f"Median {median_v:.1f}%", annotation_position="top left")
    fig.update_layout(barmode="overlay", height=350, xaxis_title="Retracement from MFE (%)",
                      yaxis_title="# Trades", hovermode="x unified",
                      showlegend=False, margin=dict(t=30))
    plot_chart(fig)


# ---------------------------------------------------------------------------
# Monthly returns tables
# ---------------------------------------------------------------------------

_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_PERCENTILES = [95, 90, 80, 70, 60, 50, 40, 30, 20, 10, 5]


def build_monthly_returns_df(equity: pd.Series) -> pd.DataFrame:
    monthly = equity.resample("ME").last()
    monthly_ret = monthly.pct_change().dropna() * 100

    years = sorted(monthly_ret.index.year.unique(), reverse=True)
    rows = []
    for yr in years:
        year_monthly_vals = []
        month_vals: Dict[str, Any] = {}
        for m_i, m_name in enumerate(_MONTHS, start=1):
            mask = (monthly_ret.index.year == yr) & (monthly_ret.index.month == m_i)
            vals = monthly_ret[mask]
            if len(vals) > 0:
                v = float(vals.iloc[0])
                month_vals[m_name] = fmt_pct(v)
                year_monthly_vals.append(v)
            else:
                month_vals[m_name] = ""

        if year_monthly_vals:
            compound = 1.0
            for v in year_monthly_vals:
                compound *= (1 + v / 100)
            annual = fmt_pct((compound - 1) * 100)
        else:
            annual = ""

        rows.append({"Year": str(yr), "Annual": annual, **month_vals})

    return pd.DataFrame(rows)


def style_monthly_table(df: pd.DataFrame) -> "pd.io.formats.style.Styler":
    def _cell_style(val):
        if not isinstance(val, str) or val == "":
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

    color_cols = [c for c in _MONTHS + ["Annual"] if c in df.columns]
    return df.style.applymap(_cell_style, subset=color_cols)


def build_monthly_stats_df(equity: pd.Series) -> pd.DataFrame:
    monthly = equity.resample("ME").last()
    monthly_ret = monthly.pct_change().dropna() * 100

    rows = []
    for m_i, m_name in enumerate(_MONTHS, start=1):
        vals = monthly_ret[monthly_ret.index.month == m_i].tolist()
        row: Dict[str, Any] = {"Month": m_name}
        if vals:
            for p in _PERCENTILES:
                row[f"P{p}"] = fmt_pct(float(np.percentile(vals, p)))
        else:
            for p in _PERCENTILES:
                row[f"P{p}"] = "—"
        rows.append(row)
    return pd.DataFrame(rows)


def style_monthly_stats_df(df: pd.DataFrame) -> "pd.io.formats.style.Styler":
    color_cols = [f"P{p}" for p in _PERCENTILES if f"P{p}" in df.columns]

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


def build_trade_entry_month_stats_df(trades, value_attr: str = "return_pct") -> pd.DataFrame:
    closed = [t for t in trades if t.status == "closed" and getattr(t, value_attr) is not None]

    rows = []
    for m_i, m_name in enumerate(_MONTHS, start=1):
        month_vals = [getattr(t, value_attr) for t in closed if t.entry_date.month == m_i]
        row: Dict[str, Any] = {"Month": m_name, "# Trades": len(month_vals)}
        if month_vals:
            for p in _PERCENTILES:
                row[f"P{p}"] = fmt_pct(float(np.percentile(month_vals, p)))
        else:
            for p in _PERCENTILES:
                row[f"P{p}"] = "—"
        rows.append(row)
    return pd.DataFrame(rows)


def render_monthly_returns_tables(
    strat_equity: pd.Series,
    bh_equity: pd.Series,
    ticker: str,
    trades: list = None,
) -> None:
    st.subheader("📅 Monthly Returns — Strategy Position")
    strat_df = build_monthly_returns_df(strat_equity)
    if strat_df.empty:
        st.info("Not enough data for monthly breakdown.")
    else:
        st.dataframe(style_monthly_table(strat_df), hide_index=True,
                     use_container_width=True, height=38 + len(strat_df) * 35)

    st.subheader("📅 Monthly Returns — Buy & Hold Position")
    bh_df = build_monthly_returns_df(bh_equity)
    if bh_df.empty:
        st.info("Not enough data for monthly breakdown.")
    else:
        st.dataframe(style_monthly_table(bh_df), hide_index=True,
                     use_container_width=True, height=38 + len(bh_df) * 35)

    st.divider()

    st.subheader("📊 Monthly Statistics — Strategy Position")
    strat_stats = build_monthly_stats_df(strat_equity)
    st.dataframe(style_monthly_stats_df(strat_stats), hide_index=True,
                 use_container_width=True, height=38 + 12 * 35)

    st.subheader("📊 Monthly Statistics — Buy & Hold Position")
    bh_stats = build_monthly_stats_df(bh_equity)
    st.dataframe(style_monthly_stats_df(bh_stats), hide_index=True,
                 use_container_width=True, height=38 + 12 * 35)

    if trades:
        st.divider()
        st.subheader("📊 Monthly Statistics — Return by Trade Entry Month")
        st.caption("Percentile distribution of trade returns grouped by the month the position was opened.")
        entry_stats = build_trade_entry_month_stats_df(trades, "return_pct")
        st.dataframe(style_monthly_stats_df(entry_stats), hide_index=True,
                     use_container_width=True, height=38 + 12 * 35)

        st.subheader("📊 Monthly Statistics — MFE by Trade Entry Month")
        st.caption("Percentile distribution of Maximum Favorable Excursion grouped by the month the position was opened.")
        mfe_stats = build_trade_entry_month_stats_df(trades, "mfe_pct")
        st.dataframe(style_monthly_stats_df(mfe_stats), hide_index=True,
                     use_container_width=True, height=38 + 12 * 35)


# ---------------------------------------------------------------------------
# Deterioration section
# ---------------------------------------------------------------------------

def render_deterioration_section(trades, strat_equity: pd.Series, ticker: str) -> None:
    closed = [
        t for t in trades
        if t.status == "closed" and t.return_pct is not None and t.entry_date is not None
    ]

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
        ANNUAL_PERCENTILES = [90, 80, 70, 60, 50, 40, 30, 20, 10]

        year_trades: dict = defaultdict(list)
        for t in sorted(closed, key=lambda x: x.entry_date):
            year_trades[t.entry_date.year].append(t.return_pct)

        annual_rows = []
        for yr in sorted(year_trades.keys(), reverse=True):
            rets = year_trades[yr]
            wins = [r for r in rets if r > 0]
            losses = [r for r in rets if r <= 0]

            capital = 1000.0
            for r in rets:
                capital *= (1 + r / 100)
            total_return_pct = (capital / 1000.0 - 1) * 100

            row: Dict[str, Any] = {
                "Year": str(yr),
                "Trades": len(rets),
                "Total Return (%)": fmt_pct(total_return_pct),
                "Win Rate": fmt_pct(len(wins) / len(rets) * 100),
                "Avg. Win (%)": fmt_pct(float(np.mean(wins))) if wins else "—",
                "Avg. Loss (%)": fmt_pct(float(np.mean(losses))) if losses else "—",
            }
            for p in ANNUAL_PERCENTILES:
                row[f"P{p}"] = fmt_pct(float(np.percentile(rets, p)))
            row["_total_return_num"] = total_return_pct
            annual_rows.append(row)

        ann_df = pd.DataFrame(annual_rows)
        display_df = ann_df.drop(columns=["_total_return_num"])

        pct_cols = (
            ["Total Return (%)", "Avg. Win (%)", "Avg. Loss (%)"]
            + [f"P{p}" for p in ANNUAL_PERCENTILES]
        )

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
            line=dict(color=PLOTLY_POSITIVE, width=2),
            hovertemplate="Win Rate: %{y:.1f}%<extra></extra>",
        ))
        fig_roll.add_hline(y=50, line_dash="dot", line_color="gray", line_width=1)
        fig_roll.update_layout(height=280, yaxis_title="Win Rate (%)",
                               hovermode="x unified", margin=dict(t=20, b=20), showlegend=True)
        plot_chart(fig_roll)

        fig_avg = go.Figure()
        fig_avg.add_trace(go.Scatter(
            x=dates, y=roll_avg, mode="lines", name="Rolling Avg Return (%)",
            line=dict(color="#FBBF24", width=2),
            hovertemplate="Avg Return: %{y:.2f}%<extra></extra>",
        ))
        fig_avg.add_hline(y=0, line_dash="dot", line_color="gray", line_width=1)
        fig_avg.update_layout(height=280, yaxis_title="Avg Return (%)",
                              hovermode="x unified", margin=dict(t=20, b=20), showlegend=True)
        plot_chart(fig_avg)

        wl_log = st.checkbox("Log returns", value=False, key=f"wl_log_{ticker}")

        def _to_log(v):
            return np.log1p(v / 100) * 100 if v is not None else None

        wl_avg_win  = [_to_log(v) for v in roll_avg_win]  if wl_log else roll_avg_win
        wl_avg_loss = [_to_log(v) for v in roll_avg_loss] if wl_log else roll_avg_loss

        fig_win_loss = go.Figure()
        fig_win_loss.add_trace(go.Scatter(
            x=dates, y=wl_avg_win, mode="lines", name="Rolling Avg. Win (%)",
            line=dict(color=PLOTLY_POSITIVE, width=2), connectgaps=False,
            hovertemplate="Avg Win: %{y:.2f}%<extra></extra>",
        ))
        fig_win_loss.add_trace(go.Scatter(
            x=dates, y=wl_avg_loss, mode="lines", name="Rolling Avg. Loss (%)",
            line=dict(color=PLOTLY_NEGATIVE, width=2), connectgaps=False,
            hovertemplate="Avg Loss: %{y:.2f}%<extra></extra>",
        ))
        fig_win_loss.add_hline(y=0, line_dash="dot", line_color="gray", line_width=1)
        fig_win_loss.update_layout(
            height=280,
            yaxis_title="Log Return (%)" if wl_log else "Return (%)",
            hovermode="x unified", margin=dict(t=20, b=20), showlegend=True,
        )
        plot_chart(fig_win_loss)

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

        first_date = dates[0]
        x_days = np.array([(d - first_date).days for d in dates], dtype=float)
        y = np.array(plot_rets, dtype=float)
        coeffs = np.polyfit(x_days, y, 1)
        trend_y = np.polyval(coeffs, x_days)
        slope_per_month = coeffs[0] * 30

        win_dates  = [d for d, r in zip(dates, plot_rets) if r > 0]
        win_rets   = [r for r in plot_rets if r > 0]
        loss_dates = [d for d, r in zip(dates, plot_rets) if r <= 0]
        loss_rets  = [r for r in plot_rets if r <= 0]

        def _hover(d, r):
            return f"{d.strftime('%Y-%m-%d')}<br>Return: {r:+.2f}%"

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
        fig_scatter.add_hrect(y0=-2, y1=2, fillcolor="rgba(255,255,255,0.03)",
                              line_width=0, layer="below")
        fig_scatter.add_hline(y=0, line_color="rgba(255,255,255,0.25)", line_width=1)

        if win_dates:
            fig_scatter.add_trace(go.Scatter(
                x=win_dates, y=win_rets, mode="markers", name="Win",
                marker=dict(color="rgba(74, 222, 128, 0.85)", size=_sizes(win_rets),
                            line=dict(color="rgba(74,222,128,0.4)", width=1), symbol="circle"),
                text=[_hover(d, r) for d, r in zip(win_dates, win_rets)],
                hovertemplate="%{text}<extra></extra>",
            ))

        if loss_dates:
            fig_scatter.add_trace(go.Scatter(
                x=loss_dates, y=loss_rets, mode="markers", name="Loss",
                marker=dict(color="rgba(248, 113, 113, 0.85)", size=_sizes(loss_rets),
                            line=dict(color="rgba(248,113,113,0.4)", width=1), symbol="circle"),
                text=[_hover(d, r) for d, r in zip(loss_dates, loss_rets)],
                hovertemplate="%{text}<extra></extra>",
            ))

        fig_scatter.add_trace(go.Scatter(
            x=dates, y=trend_y.tolist(), mode="lines", name="Trend",
            line=dict(color=trend_color, width=4), opacity=0.25,
            showlegend=False, hoverinfo="skip",
        ))
        fig_scatter.add_trace(go.Scatter(
            x=dates, y=trend_y.tolist(), mode="lines",
            name=f"Trend ({direction} {slope_per_month:+.2f}% / month)",
            line=dict(color=trend_color, width=2, dash="dot"),
            hovertemplate="Trend: %{y:.2f}%<extra></extra>",
        ))

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
        plot_chart(fig_scatter)

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
        fig_r12.add_trace(go.Scatter(
            x=rolling_12m.index, y=rolling_12m.clip(lower=0),
            fill="tozeroy", mode="none", name="Positive",
            fillcolor="rgba(34, 197, 94, 0.25)",
        ))
        fig_r12.add_trace(go.Scatter(
            x=rolling_12m.index, y=rolling_12m.clip(upper=0),
            fill="tozeroy", mode="none", name="Negative",
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
            height=400,
            yaxis_title="Trailing 12M Log Return (%)" if r12_log else "Trailing 12M Return (%)",
            hovermode="x unified", showlegend=True, margin=dict(t=30),
        )
        plot_chart(fig_r12)
