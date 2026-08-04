"""Tests for cross-universe reuse in the market-history refresh script."""
from __future__ import annotations

from datetime import date

import pandas as pd

from scripts import refresh_market_history


def _rows(symbol: str, dates: list[str], closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame({
        "symbol": symbol,
        "date": pd.to_datetime(dates),
        "open": closes,
        "high": closes,
        "low": closes,
        "close": closes,
        "volume": 1_000.0,
    })


def test_us2000_snapshot_contains_official_listed_equity_holdings():
    symbols = refresh_market_history._symbols("US2000")

    assert len(symbols) == 1954
    assert "MOG-A" in symbols
    assert "CRD-A" in symbols


def test_us_download_plan_skips_current_symbols_and_only_fetches_stale_delta():
    existing = pd.concat([
        _rows("CURRENT", ["2021-01-04", "2026-08-03"], [10.0, 20.0]),
        _rows("STALE", ["2021-01-04", "2026-07-24"], [10.0, 20.0]),
    ])

    plan = refresh_market_history._market_download_plan(
        existing,
        ["CURRENT", "STALE", "MISSING"],
        date(2021, 1, 1),
        date(2026, 8, 3),
        "incremental",
    )

    assert "CURRENT" not in {symbol for group in plan.values() for symbol in group}
    assert plan[date(2026, 7, 17)] == ["STALE"]
    assert plan[date(2021, 1, 1)] == ["MISSING"]


def test_us_download_plan_treats_weekend_cache_as_current():
    existing = _rows("AAA", ["2021-01-04", "2026-07-31"], [10.0, 20.0])

    plan = refresh_market_history._market_download_plan(
        existing,
        ["AAA"],
        date(2021, 1, 1),
        date(2026, 8, 2),
        "incremental",
    )

    assert plan == {}


def test_full_download_plan_can_trust_cache_rebuilt_earlier_in_same_run():
    existing = _rows("OVERLAP", ["2006-12-13", "2026-07-31"], [10.0, 20.0])

    plan = refresh_market_history._market_download_plan(
        existing,
        ["OVERLAP", "NEW"],
        date(1900, 1, 1),
        date(2026, 8, 1),
        "full",
        assume_existing_complete=True,
    )

    assert plan == {date(1900, 1, 1): ["NEW"]}
