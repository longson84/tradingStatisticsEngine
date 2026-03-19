"""Shared analytics on portfolio/positions — no Streamlit."""
from src.backtest.performance import TradePerformance, calculate_trade_performance
from src.backtest.drawdown import (
    calculate_drawdown_during_trades,
    calculate_max_drawdown,
    calculate_equity_curve_max_drawdown,
)

__all__ = [
    "TradePerformance",
    "calculate_trade_performance",
    "calculate_drawdown_during_trades",
    "calculate_max_drawdown",
    "calculate_equity_curve_max_drawdown",
]
