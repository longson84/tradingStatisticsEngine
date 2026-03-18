"""AHR999 signal — BTC-USD only."""
import pandas as pd

from src.signals.base import BaseSignal
from src.indicators.ahr999 import ahr999


class AHR999Signal(BaseSignal):
    def __init__(self):
        self._name = "AHR999"

    @property
    def name(self) -> str:
        return self._name

    def is_applicable(self, ticker: str) -> bool:
        return ticker == "BTC-USD"

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        return ahr999(df['Close'])
