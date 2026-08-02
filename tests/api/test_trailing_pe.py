from __future__ import annotations

import pandas as pd

from api.fundamentals_cache import (
    load_cached_fundamentals,
    refresh_symbol_fundamentals,
)


def test_fundamentals_cache_is_persistent_and_read_does_not_refetch(tmp_path, monkeypatch):
    expected = pd.DataFrame({
        "effective_date": pd.to_datetime(["2026-05-01"]),
        "eps_ttm": [5.0],
        "period_end": pd.to_datetime(["2026-03-31"]),
        "period": ["2026-Q1"],
        "book_value_per_share": [20.0],
    })
    calls = 0

    def fetch(symbol):
        nonlocal calls
        calls += 1
        return expected, "test method"

    monkeypatch.setattr("api.fundamentals_cache._fetch_us_fundamentals", fetch)

    first, first_manifest = refresh_symbol_fundamentals(
        "AAPL", "US", cache_dir=tmp_path
    )
    second, second_manifest = load_cached_fundamentals(
        "AAPL", "US", cache_dir=tmp_path
    )

    assert calls == 1
    assert first["eps_ttm"].tolist() == [5.0]
    assert second["eps_ttm"].tolist() == [5.0]
    assert first_manifest == second_manifest


def test_refresh_merges_new_period_without_removing_history(tmp_path, monkeypatch):
    responses = iter([
        pd.DataFrame({
            "effective_date": pd.to_datetime(["2025-05-01"]),
            "period_end": pd.to_datetime(["2025-03-31"]),
            "period": ["2025-Q1"],
            "eps_ttm": [4.0],
        }),
        pd.DataFrame({
            "effective_date": pd.to_datetime(["2025-08-01"]),
            "period_end": pd.to_datetime(["2025-06-30"]),
            "period": ["2025-Q2"],
            "eps_ttm": [4.5],
        }),
    ])
    monkeypatch.setattr(
        "api.fundamentals_cache._fetch_us_fundamentals",
        lambda symbol: (next(responses), "test method"),
    )

    refresh_symbol_fundamentals("AAPL", "US", cache_dir=tmp_path)
    merged, _ = refresh_symbol_fundamentals("AAPL", "US", cache_dir=tmp_path)

    assert merged["period"].tolist() == ["2025-Q1", "2025-Q2"]
    assert merged["eps_ttm"].tolist() == [4.0, 4.5]
