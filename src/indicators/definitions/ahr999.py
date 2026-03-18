"""AHR999 indicator — BTC-USD only."""
from datetime import datetime

import numpy as np
import pandas as pd

from src.indicators.base import BaseIndicator


class AHR999Indicator(BaseIndicator):
    def __init__(self):
        self._name = "AHR999"

    @property
    def name(self) -> str:
        return self._name

    @property
    def report_name(self) -> str:
        return "AHR999"

    def is_applicable(self, ticker: str) -> bool:
        return ticker == "BTC-USD"

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        data = df.copy()
        genesis_date = datetime(2009, 1, 3)
        days_passed = (data.index - genesis_date).days
        days_passed = np.maximum(days_passed, 1)

        p_est = 10 ** (5.84 * np.log10(days_passed) - 17.01)
        ma200 = data['Close'].rolling(window=200).mean()

        ahr_values = (data['Close'] / p_est) * (data['Close'] / ma200)
        return ahr_values.dropna()
