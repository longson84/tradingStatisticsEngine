"""Shared market-session calendar helpers for application freshness checks."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


def latest_completed_session(now: datetime, market: str) -> date:
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    normalized = market.upper().strip()
    if normalized not in {"US", "VN"}:
        raise ValueError("Market must be US or VN")
    timezone = ZoneInfo(
        "Asia/Ho_Chi_Minh" if normalized == "VN" else "America/New_York"
    )
    local = now.astimezone(timezone)
    close = time(15, 15) if normalized == "VN" else time(16, 15)
    candidate = (
        local.date()
        if local.time() >= close
        else local.date() - timedelta(days=1)
    )
    while candidate.weekday() >= 5:
        candidate -= timedelta(days=1)
    return candidate
