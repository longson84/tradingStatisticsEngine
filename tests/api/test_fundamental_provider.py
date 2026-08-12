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
        lambda symbol, provider=None: (frame, "vci", f"VN {symbol}"),
    )

    us_frame, us_source, us_method = (
        fundamental_provider.fetch_provider_fundamentals("aapl", "yfinance")
    )
    vn_frame, vn_source, vn_method = (
        fundamental_provider.fetch_provider_fundamentals("fpt", "vnstock_data")
    )

    assert us_frame is frame
    assert (us_source, us_method) == ("yfinance", "US AAPL")
    assert vn_frame is frame
    assert (vn_source, vn_method) == ("vci", "VN FPT")


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


def test_sponsored_vci_reports_preserve_point_in_time_quarters():
    ratios = pd.DataFrame({
        "ratioTtmId": [101, 102, 199, 201],
        "ratioYearId": [pd.NA, pd.NA, 199, pd.NA],
        "ratioType": ["RATIO_TTM", "RATIO_TTM", "RATIO_YEAR", "RATIO_TTM"],
        "year": [2025, 2025, 2025, 2026],
        "quarter": [1, 3, 5, 1],
        "yearReport": [2025, 2025, 2025, 2026],
        "numberOfSharesMktCap": [100.0, 100.0, 100.0, 110.0],
        "marketCap": [1_000.0, 1_200.0, 1_100.0, 1_430.0],
        "pe": [10.0, 12.0, 11.0, 13.0],
        "pb": [2.0, 2.4, 2.2, 2.6],
        "ps": [1.0, 1.2, 1.1, 1.3],
        "roe": [0.20, 0.21, 0.20, 0.22],
    })
    income = pd.DataFrame({
        "yearReport": [2025, 2025, 2025, 2025, 2026],
        "lengthReport": [1, 2, 3, 4, 1],
        "publicDate": [
            "2025-04-20", "2025-07-20", "2025-10-20", "2026-03-20",
            "2026-04-28",
        ],
    })

    frame = fundamental_provider._normalize_vn_fundamental_reports(
        ratios, income
    )

    assert frame["period"].tolist() == ["2025-Q1", "2025-Q3", "2026-Q1"]
    assert frame["effective_date"].dt.strftime("%Y-%m-%d").tolist() == [
        "2025-04-21", "2025-10-21", "2026-04-29"
    ]
    # Output is ordered by effective availability, not fiscal period.
    assert frame.sort_values("effective_date")["period"].tolist() == [
        "2025-Q1", "2025-Q3", "2026-Q1"
    ]
    q3 = frame.loc[frame["period"] == "2025-Q3"].iloc[0]
    assert q3["eps_ttm"] == 1.0
    assert q3["book_value_per_share"] == 5.0
