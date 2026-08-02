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


def test_reusable_us_history_prefers_cache_with_newer_symbol_data(monkeypatch):
    caches = {
        "US500": _rows("AAA", ["2026-07-30", "2026-07-31"], [10.0, 11.0]),
        "US100": _rows(
            "AAA",
            ["2026-07-30", "2026-07-31", "2026-08-03"],
            [20.0, 21.0, 22.0],
        ),
    }
    monkeypatch.setattr(
        refresh_market_history,
        "_existing_cache",
        lambda universe: caches.get(universe, pd.DataFrame()),
    )

    result = refresh_market_history._reusable_us_history(
        "US500",
        ["AAA"],
        include_target=True,
    )

    assert result["date"].max().date() == date(2026, 8, 3)
    assert result.loc[result["date"] == "2026-07-30", "close"].item() == 20.0


def test_reusable_vn_history_prefers_newer_vn100_overlap(monkeypatch):
    caches = {
        "VN30": _rows("FPT", ["2026-07-30", "2026-07-31"], [10.0, 11.0]),
        "VN100": _rows(
            "FPT",
            ["2026-07-30", "2026-07-31", "2026-08-03"],
            [20.0, 21.0, 22.0],
        ),
    }
    monkeypatch.setattr(
        refresh_market_history,
        "_existing_cache",
        lambda universe: caches.get(universe, pd.DataFrame()),
    )

    result = refresh_market_history._reusable_vn_history(
        "VN30",
        ["FPT"],
        include_target=True,
    )

    assert result["date"].max().date() == date(2026, 8, 3)
    assert result.loc[result["date"] == "2026-07-30", "close"].item() == 20.0


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


def test_explicit_empty_reuse_set_ignores_older_related_caches(monkeypatch):
    monkeypatch.setattr(
        refresh_market_history,
        "_existing_cache",
        lambda universe: _rows("AAA", ["2020-01-02"], [10.0]),
    )

    result = refresh_market_history._reusable_us_history(
        "US2000",
        ["AAA"],
        include_target=False,
        reuse_from=(),
    )

    assert result.empty
