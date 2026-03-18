"""Distance from Peak signal."""
import pandas as pd

from src.signals.base import BaseSignal
from src.indicators.peak import distance_from_peak
from src.shared.constants import DATE_FORMAT_DISPLAY
from src.shared.fmt import fmt_pct, fmt_price


class DistanceFromPeakSignal(BaseSignal):
    def __init__(self, window_days: int = None):
        self.window = window_days
        if window_days:
            self._name = f"Khoảng cách đến đỉnh {window_days}D"
        else:
            self._name = "Khoảng cách từ đỉnh (Tùy chỉnh)"

    @property
    def name(self) -> str:
        return self._name

    @property
    def report_name(self) -> str:
        return f"Dist_Peak_{self.window}D"

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        return distance_from_peak(df['Close'], self.window).dropna()

    def format_value(self, value: float) -> str:
        return fmt_pct(-value * 100)

    def get_additional_info(self, df: pd.DataFrame) -> dict:
        recent_data = df.tail(self.window)

        if recent_data.empty:
            return super().get_additional_info(df)

        peak_price = recent_data['Close'].max()
        peak_date = recent_data['Close'].idxmax()
        current_date = df.index[-1]

        days_since_ref = len(df.loc[peak_date:current_date]) - 1
        days_remaining = self.window - days_since_ref

        return {
            "ref_date": peak_date.strftime(DATE_FORMAT_DISPLAY),
            "ref_value": fmt_price(peak_price),
            "days_since_ref": days_since_ref,
            "days_remaining": days_remaining,
        }
