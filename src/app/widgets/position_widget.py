"""Streamlit rendering helpers specific to the position backtest pack."""
import pandas as pd
import streamlit as st

from src.shared.constants import COLOR_ACTIVE, NONNEG_BUCKETS, RETURN_BUCKETS
from src.shared.fmt import fmt_capture, fmt_pct

from src.backtest.charts import build_equity_chart
from src.backtest.tables import build_trade_log_df

from src.app.ui import plot_chart
from src.app.styling import style_capture, style_positive_negative
from src.app.packs._renderers import render_distribution


def render_current_position(pos) -> None:
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


def render_bh_comparison(perf, strat_max_drawdown, bh_total_return, bh_max_drawdown) -> None:
    st.subheader("📈 Strategy vs Buy & Hold")
    capture = perf.total_return / bh_total_return if bh_total_return and bh_total_return > 0 else None
    cmp_data = {
        "Metric":     ["Total Return (%)", "Max Drawdown (%)"],
        "Strategy":   [fmt_pct(perf.total_return), fmt_pct(strat_max_drawdown)],
        "Buy & Hold": [fmt_pct(bh_total_return),   fmt_pct(bh_max_drawdown)],
        "Capture":    [fmt_capture(capture),        ""],
    }
    cmp_df = pd.DataFrame(cmp_data)
    styled_cmp = cmp_df.style.applymap(style_capture, subset=["Capture"])
    st.dataframe(styled_cmp, hide_index=True, use_container_width=True, height=38 + 2 * 35)


def render_trade_log(trades, bh_equity) -> None:
    st.subheader("📋 Trade Log")
    if not trades:
        st.info("No trades generated.")
        return

    trade_df = build_trade_log_df(trades, bh_equity)
    sorted_trades = sorted(trades, key=lambda x: x.entry_date, reverse=True)
    returns_numeric = [t.return_pct for t in sorted_trades]
    statuses = [t.status for t in sorted_trades]

    def _row_style(row: pd.Series):
        if statuses[row.name] == "open":
            return [COLOR_ACTIVE] * len(row)
        return [style_positive_negative(returns_numeric[row.name])] * len(row)

    styled = trade_df.style.apply(_row_style, axis=1)
    st.dataframe(styled, use_container_width=True, hide_index=True, height=38 + min(len(trade_df), 20) * 35)


def render_distributions(trades) -> None:
    closed = [t for t in trades if t.status == "closed" and t.return_pct is not None]
    winners = [t for t in closed if t.return_pct > 0]

    st.subheader("📊 Return Distribution")
    render_distribution([t.return_pct for t in closed], "Return", RETURN_BUCKETS, bucket_header="Return buckets")

    st.subheader("📉 MAE of Winning Trades")
    st.caption("How far winning trades drew down before recovering.")
    render_distribution([t.mae_pct for t in winners if t.mae_pct is not None], "MAE %", NONNEG_BUCKETS)

    st.subheader("📈 MFE of Winning Trades")
    st.caption("Peak unrealized gain reached during winning trades.")
    render_distribution([t.mfe_pct for t in winners if t.mfe_pct is not None], "MFE %", NONNEG_BUCKETS)


def render_equity_curve(ticker, strat_equity, bh_equity, strategy_label) -> None:
    st.subheader("📈 Equity Curve")
    log_scale = st.checkbox("Log scale (Y axis)", value=False, key=f"strat_log_scale_{ticker}")
    fig = build_equity_chart(ticker, strat_equity, bh_equity, strategy_label, log_scale)
    plot_chart(fig)
