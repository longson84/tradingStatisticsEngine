"""Shared API utilities."""
from __future__ import annotations


def date_key(ts) -> str:
    """Convert pandas Timestamp or date to ISO string key.

    Args:
        ts: A pandas Timestamp, datetime.date, or any object with a .date() method.

    Returns:
        ISO format date string (YYYY-MM-DD).
    """
    return str(ts.date()) if hasattr(ts, "date") and callable(ts.date) else str(ts)
