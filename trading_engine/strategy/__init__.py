"""Strategy layer — weight-matrix-based trading strategies.

All strategies implement the Strategy Protocol via BaseStrategy.
They output a weight matrix (time x symbols, values in [-1, 1]).
"""
from trading_engine.strategy.base import BaseStrategy
from trading_engine.strategy.ma_crossover import MACrossover
from trading_engine.strategy.buy_and_hold import BuyAndHold
from trading_engine.strategy.ensemble import EnsembleStrategy

__all__ = [
    "BaseStrategy",
    "MACrossover",
    "BuyAndHold",
    "EnsembleStrategy",
]
