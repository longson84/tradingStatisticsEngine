"""Signals — named, configured time series derived from price data."""
from src.signals.base import BaseSignal
from src.signals.ahr999 import AHR999Signal
from src.signals.distance_from_peak import DistanceFromPeakSignal
from src.signals.ma_ratio import MARatioSignal

SIGNAL_REGISTRY: dict[str, type] = {
    "AHR999": AHR999Signal,
    "DistanceFromPeak": DistanceFromPeakSignal,
    "MARatio": MARatioSignal,
}

__all__ = [
    "BaseSignal",
    "AHR999Signal",
    "DistanceFromPeakSignal",
    "MARatioSignal",
    "SIGNAL_REGISTRY",
]
