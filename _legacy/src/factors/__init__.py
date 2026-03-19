"""Factors — named, configured time series derived from price data."""
from src.factors.base import BaseFactor
from src.factors.ahr999 import AHR999Factor
from src.factors.distance_from_peak import DistanceFromPeakFactor
from src.factors.ma_ratio import MARatioFactor

FACTOR_REGISTRY: dict[str, type] = {
    "AHR999": AHR999Factor,
    "DistanceFromPeak": DistanceFromPeakFactor,
    "MARatio": MARatioFactor,
}

__all__ = [
    "BaseFactor",
    "AHR999Factor",
    "DistanceFromPeakFactor",
    "MARatioFactor",
    "FACTOR_REGISTRY",
]
