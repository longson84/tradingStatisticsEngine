"""Performance layer — analysis + comparison framework."""
from trading_engine.performance.analyzer import analyze_performance
from trading_engine.performance.comparison import run_comparison
from trading_engine.performance.strategy_analysis import run_single_ticker_analysis

__all__ = ["analyze_performance", "run_comparison", "run_single_ticker_analysis"]
