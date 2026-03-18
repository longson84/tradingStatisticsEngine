"""BaseSignal — abstract base class for all signal types."""
import pandas as pd
from abc import ABC, abstractmethod


class BaseSignal(ABC):
    """Abstract base class for all signals.

    A signal is a named, configured time series derived from price data
    (via indicator functions) or any other source. Signals are consumed
    by the analysis layer.
    """

    @abstractmethod
    def calculate(self, price: pd.DataFrame) -> pd.Series:
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    def get_additional_info(self, price: pd.DataFrame) -> dict:
        """Return supplementary info (ref_date, ref_value, etc.)."""
        return None

    def format_value(self, value: float) -> str:
        """Format a signal value for display."""
        return f"{value:.2f}"

    def is_applicable(self, ticker: str) -> bool:
        """Check whether this signal applies to the given ticker."""
        return True
