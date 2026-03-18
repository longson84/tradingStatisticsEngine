"""MA Ratio factor (Price / MA - 1)."""
from typing import Literal

import pandas as pd

from src.factors.base import BaseFactor
from src.indicators.ma import moving_average
from src.shared.constants import DATE_FORMAT_DISPLAY
from src.shared.fmt import fmt_pct, fmt_price


class MARatioFactor(BaseFactor):
    def __init__(self, ma_type: Literal["SMA", "EMA", "WMA"], length: int):
        self.ma_type = ma_type
        self.length = length

    @property
    def name(self) -> str:
        return f"{self.ma_type}({self.length}) vs Price"

    def calculate(self, price: pd.DataFrame) -> pd.Series:
        ma = moving_average(price['Close'], self.ma_type, self.length)
        return (price['Close'] / ma - 1).dropna()

    def format_value(self, value: float) -> str:
        return fmt_pct(value * 100)

    def get_additional_info(self, price: pd.DataFrame) -> dict:
        ma = moving_average(price['Close'], self.ma_type, self.length)
        ma_value = ma.iloc[-1]
        return {
            "ref_date": ma.index[-1].strftime(DATE_FORMAT_DISPLAY),
            "ref_value": f"{fmt_price(ma_value)} ({self.ma_type}{self.length})",
            "days_since_ref": 0,
        }
