"""trading_engine — a standalone Python library for strategy backtesting.

Five top-level imports cover all use cases:

    from trading_engine import (
        run_portfolio,    # single config -> PortfolioResult
        run_comparison,   # N configs + prices -> ComparisonReport
        analyze_factor,   # time-series factor analysis
        analyze_universe, # cross-sectional + regime
        detect_regime,    # breadth -> RegimeSeries
    )

Zero Streamlit imports. Works in Jupyter, CLI, and FastAPI equally well.
"""
from trading_engine.portfolio.simulation import run_portfolio
from trading_engine.performance.comparison import run_comparison
from trading_engine.factor_analysis.time_series import percentile_breakdown as analyze_factor
from trading_engine.factor_analysis.cross_sectional import analyze_cross_section as analyze_universe
from trading_engine.factor_analysis.regime import detect_regime

__all__ = [
    "run_portfolio",
    "run_comparison",
    "analyze_factor",
    "analyze_universe",
    "detect_regime",
]
