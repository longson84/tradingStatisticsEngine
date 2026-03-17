"""Strategy registry — add new strategies to the list below only."""
from typing import List

from src.strategy.strategies.base import BaseStrategy
from src.strategy.strategies.price_vs_ma import PriceVsMAStrategy
from src.strategy.strategies.ma_crossover import MACrossoverStrategy
from src.strategy.strategies.donchian_breakout import DonchianBreakoutStrategy
from src.strategy.strategies.bollinger_bands import BollingerBandStrategy

STRATEGY_REGISTRY: dict[str, type[BaseStrategy]] = {
    cls.DISPLAY_NAME: cls
    for cls in [PriceVsMAStrategy, MACrossoverStrategy, DonchianBreakoutStrategy, BollingerBandStrategy]
}

STRATEGY_NAMES: List[str] = list(STRATEGY_REGISTRY)

__all__ = [
    "BaseStrategy",
    "PriceVsMAStrategy",
    "MACrossoverStrategy",
    "DonchianBreakoutStrategy",
    "BollingerBandStrategy",
    "STRATEGY_REGISTRY",
    "STRATEGY_NAMES",
]
