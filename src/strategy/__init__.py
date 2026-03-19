"""Strategy package — trade signal generation only, no Streamlit."""
from src.strategy.base import BaseStrategy
from src.strategy.registry import STRATEGY_REGISTRY, STRATEGY_NAMES
from src.strategy.strategy_utils import generate_trade_signals
from src.strategy.price_vs_ma import PriceVsMAStrategy
from src.strategy.ma_crossover import MACrossoverStrategy
from src.strategy.donchian_breakout import DonchianBreakoutStrategy
from src.strategy.bollinger_bands import BollingerBandStrategy
__all__ = [
    "BaseStrategy",
    "STRATEGY_REGISTRY",
    "STRATEGY_NAMES",
    "generate_trade_signals",
    "PriceVsMAStrategy",
    "MACrossoverStrategy",
    "DonchianBreakoutStrategy",
    "BollingerBandStrategy",
]
