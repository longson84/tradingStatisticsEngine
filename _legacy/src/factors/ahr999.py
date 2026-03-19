"""AHR999 factor — BTC-USD only."""
import pandas as pd

from src.factors.base import BaseFactor
from src.indicators.ahr999 import ahr999


class AHR999Factor(BaseFactor):
    def __init__(self):
        self._name = "AHR999"

    @property
    def name(self) -> str:
        return self._name

    def is_applicable(self, ticker: str) -> bool:
        return ticker == "BTC-USD"

    def calculate(self, price: pd.DataFrame) -> pd.Series:
        return ahr999(price['Close'])
