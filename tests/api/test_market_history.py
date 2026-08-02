"""Tests for persistent market-history cache loading."""
from __future__ import annotations

import json

import pandas as pd
import pytest

from api.market_history import (
    load_cached_market_history,
    load_cached_market_symbol,
    save_market_history,
)


@pytest.mark.parametrize("universe", ["US500", "US2000", "US100", "VN100", "VN30"])
def test_market_history_cache_round_trip(tmp_path, universe):
    dates = pd.date_range("2024-01-01", periods=3, freq="B")
    rows = pd.DataFrame(
        {
            "symbol": ["A"] * 3,
            "date": dates,
            "open": [10.0, 11.0, 12.0],
            "high": [10.0, 11.0, 12.0],
            "low": [10.0, 11.0, 12.0],
            "close": [10.0, 11.0, 12.0],
            "volume": [100.0, 110.0, 120.0],
        }
    )
    manifest = {
        "universe": universe,
        "fetched_at": "2026-07-26T00:00:00+00:00",
        "first_date": "2024-01-01",
        "last_date": "2024-01-03",
        "symbol_count": 1,
        "source": "test",
        "price_basis": "adjusted",
    }

    save_market_history(universe, rows, manifest, cache_dir=tmp_path)
    prices, loaded_manifest = load_cached_market_history(
        universe,
        cache_dir=tmp_path,
    )

    assert loaded_manifest == manifest
    assert list(prices) == ["A"]
    assert prices["A"].data["close"].tolist() == [10.0, 11.0, 12.0]
    assert json.loads((tmp_path / f"{universe.lower()}.json").read_text()) == manifest


def test_load_cached_market_symbol_filters_the_universe_cache(tmp_path):
    dates = pd.date_range("2024-01-01", periods=2, freq="B")
    rows = pd.DataFrame({
        "symbol": ["AAA", "AAA", "FPT", "FPT"],
        "date": list(dates) * 2,
        "open": [1.0, 2.0, 10.0, 11.0],
        "high": [1.0, 2.0, 10.0, 11.0],
        "low": [1.0, 2.0, 10.0, 11.0],
        "close": [1.0, 2.0, 10.0, 11.0],
        "volume": [100.0, 200.0, 300.0, 400.0],
    })
    manifest = {
        "universe": "VN100",
        "fetched_at": "2026-08-01T00:00:00+00:00",
        "first_date": "2024-01-01",
        "last_date": "2024-01-02",
        "symbol_count": 2,
        "row_count": 4,
        "source": "vnstock-vci",
        "price_basis": "provider OHLC (adjustment unspecified)",
    }
    save_market_history("VN100", rows, manifest, cache_dir=tmp_path)

    prices, loaded_manifest = load_cached_market_symbol(
        "vn100", "fpt", cache_dir=tmp_path, chunksize=1
    )

    assert prices.symbol == "FPT"
    assert prices.data["close"].tolist() == [10.0, 11.0]
    assert loaded_manifest == manifest
