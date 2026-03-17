"""Performance summary metrics renderer."""
import streamlit as st

from src.constants import fmt_pct


def render_performance_summary(perf, max_drawdown: float = 0.0) -> None:
    """Render strategy performance metrics (win rate, returns, trade counts, etc.)."""
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total Return", fmt_pct(perf.total_return))
    m2.metric("Win Rate", fmt_pct(perf.win_rate))
    m3.metric("Avg Win", fmt_pct(perf.avg_winning_return) if perf.avg_winning_return else "—")
    m4.metric("Avg Loss", fmt_pct(perf.avg_losing_return) if perf.avg_losing_return else "—")
    m5.metric("Max. DD", fmt_pct(max_drawdown))

    m6, m7, m8, m9, m10, m11 = st.columns(6)
    m6.metric("Closed Trades", str(perf.closed_trades))
    m7.metric("Win Trades", str(perf.win_count))
    m8.metric("Loss Trades", str(perf.loss_count))
    m9.metric("Max Consec. Loss", str(perf.max_consecutive_losses))
    m10.metric("Best Trade", fmt_pct(perf.best_trade_return))
    m11.metric("Worst Trade", fmt_pct(perf.worst_trade_return))
