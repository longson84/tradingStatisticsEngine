from __future__ import annotations

import pandas as pd

from api import fundamental_provider


def test_fetch_provider_fundamentals_selects_market_source(monkeypatch):
    frame = pd.DataFrame({"effective_date": pd.to_datetime(["2026-05-01"])})
    monkeypatch.setattr(
        fundamental_provider,
        "_fetch_us_fundamentals",
        lambda symbol: (frame, f"US {symbol}"),
    )
    monkeypatch.setattr(
        fundamental_provider,
        "_fetch_vn_fundamentals",
        lambda symbol: (frame, f"VN {symbol}"),
    )

    us_frame, us_source, us_method = (
        fundamental_provider.fetch_provider_fundamentals("aapl", "US")
    )
    vn_frame, vn_source, vn_method = (
        fundamental_provider.fetch_provider_fundamentals("fpt", "VN")
    )

    assert us_frame is frame
    assert (us_source, us_method) == ("yfinance", "US AAPL")
    assert vn_frame is frame
    assert (vn_source, vn_method) == ("vnstock-vci-4.0.5", "VN FPT")


def test_merge_provider_rows_prefers_new_non_null_values():
    existing = pd.DataFrame({
        "effective_date": pd.to_datetime(["2026-05-01"]),
        "period_end": pd.to_datetime(["2026-03-31"]),
        "period": ["2026-Q1"],
        "eps_ttm": [5.0],
        "book_value_per_share": [20.0],
    })
    fetched = pd.DataFrame({
        "effective_date": pd.to_datetime(["2026-05-01"]),
        "period_end": pd.to_datetime(["2026-03-31"]),
        "period": ["2026-Q1"],
        "eps_ttm": [5.5],
        "book_value_per_share": [pd.NA],
    })

    merged = fundamental_provider.merge_fundamentals(existing, fetched)

    assert merged["eps_ttm"].tolist() == [5.5]
    assert merged["book_value_per_share"].tolist() == [20.0]
