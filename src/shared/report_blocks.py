"""Reusable markdown/text building blocks shared across report generators and packs."""
from datetime import datetime

import pandas as pd

from src.shared.constants import DATE_FORMAT_DISPLAY


def build_report_time_range_info(prices: pd.Series) -> list[str]:
    """Return time-range info lines for a price series.

    Returns plain strings (no trailing whitespace) so callers can format
    for their own renderer — join with newlines for markdown, or '  |  ' for st.caption.
    """
    return [
        "### Khung thời gian thống kê",
        f"Ngày thống kê: {datetime.now().strftime(DATE_FORMAT_DISPLAY)}  ",
        f"Ngày dữ liệu đầu tiên: {prices.index.min().strftime(DATE_FORMAT_DISPLAY)}  ",
        f"Ngày dữ liệu cuối cùng: {prices.index[-1].strftime(DATE_FORMAT_DISPLAY)}  ",
        f"Tổng số phiên: {len(prices):,}  ",
    ]
