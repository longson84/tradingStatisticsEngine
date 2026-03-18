"""Base indicator class — renamed from BaseSignal."""
import pandas as pd
from abc import ABC, abstractmethod

from src.shared.constants import PLOTLY_ACTIVE, PLOTLY_NEGATIVE, PLOTLY_POSITIVE, VISUALIZATION_THRESHOLDS


class BaseIndicator(ABC):
    """Abstract base class for all indicator types."""

    @abstractmethod
    def calculate(self, df: pd.DataFrame) -> pd.Series:
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def report_name(self) -> str:
        """Short file-safe name for reports."""
        pass

    @property
    def visualization_config(self) -> dict:
        """Chart display configuration: thresholds and colours."""
        return {
            "thresholds": VISUALIZATION_THRESHOLDS,
            "colors": [PLOTLY_POSITIVE, PLOTLY_ACTIVE, PLOTLY_NEGATIVE],
        }

    def get_additional_info(self, df: pd.DataFrame) -> dict:
        """Return supplementary info (ref_date, ref_value, etc.)."""
        return None

    def format_value(self, value: float) -> str:
        """Format an indicator value for display."""
        return f"{value:.2f}"

    def is_applicable(self, ticker: str) -> bool:
        """Check whether this indicator applies to the given ticker."""
        return True
