"""Factor layer — all factors (indicators + analytical) unified.

A Factor is any function from prices -> derived series.
Technical indicators (MA, Bollinger, Donchian) and analytical factors
(rarity score, AHR999) are all Factors implementing the same Protocol.
"""
from trading_engine.factors.moving_average import MovingAverage, MovingAverageRatio
from trading_engine.factors.bollinger import BollingerBands
from trading_engine.factors.donchian import DonchianChannel
from trading_engine.factors.distance_from_peak import DistanceFromPeak
from trading_engine.factors.ahr999 import AHR999

__all__ = [
    "MovingAverage",
    "MovingAverageRatio",
    "BollingerBands",
    "DonchianChannel",
    "DistanceFromPeak",
    "AHR999",
]
