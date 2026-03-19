"""Reusable markdown/text building blocks shared across report generators and packs."""
from datetime import datetime

import pandas as pd

from src.shared.constants import DATE_FORMAT_DISPLAY


def build_report_time_range_info(prices: pd.Series) -> str:
    """Return a markdown string with time-range info for a price series.

    Pass directly to st.markdown().
    """
    lines = [
        "### Khung thời gian thống kê",
        f"Ngày thống kê: {datetime.now().strftime(DATE_FORMAT_DISPLAY)}  ",
        f"Ngày dữ liệu đầu tiên: {prices.index.min().strftime(DATE_FORMAT_DISPLAY)}  ",
        f"Ngày dữ liệu cuối cùng: {prices.index[-1].strftime(DATE_FORMAT_DISPLAY)}  ",
        f"Tổng số phiên: {len(prices):,}  ",
    ]
    return "\n".join(lines)
