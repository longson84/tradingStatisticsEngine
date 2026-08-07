"""Factor Analysis layer — pure functions over FactorSeries.

Two modes:
- Time-series: 1 symbol x 1 factor x time -> FactorAnalysisResult
- Cross-sectional: N symbols x 1 factor -> CrossSectionalResult + regime
"""
from trading_engine.factor_analysis.time_series import (
    percentile_breakdown,
    rarity_analysis,
)
from trading_engine.factor_analysis.cross_sectional import analyze_cross_section
from trading_engine.factor_analysis.regime import detect_regime
from trading_engine.factor_analysis.market_health import (
    compute_market_health,
    compute_market_health_from_closes,
)

__all__ = [
    "percentile_breakdown",
    "rarity_analysis",
    "analyze_cross_section",
    "detect_regime",
    "compute_market_health",
    "compute_market_health_from_closes",
]
