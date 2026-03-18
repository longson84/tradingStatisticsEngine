"""Indicator class registry."""
from src.indicators.definitions.ahr999 import AHR999Indicator
from src.indicators.definitions.distance_from_peak import DistanceFromPeakIndicator
from src.indicators.definitions.ma_ratio import MARatioIndicator

INDICATOR_REGISTRY: dict[str, type] = {
    "AHR999": AHR999Indicator,
    "DistanceFromPeak": DistanceFromPeakIndicator,
    "MARatio": MARatioIndicator,
}

__all__ = [
    "AHR999Indicator",
    "DistanceFromPeakIndicator",
    "MARatioIndicator",
    "INDICATOR_REGISTRY",
]
