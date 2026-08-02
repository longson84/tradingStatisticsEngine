from __future__ import annotations

import pandas as pd
import pytest

from trading_engine.fundamentals import (
    fundamental_growth_over_years,
    point_in_time_fundamental,
    point_in_time_trailing_pe,
    rebase_eps_to_adjusted_prices,
)


def test_fundamental_growth_uses_ten_year_snapshot_and_calculates_cagr():
    snapshots = pd.DataFrame({
        "effective_date": pd.to_datetime(["2015-01-01", "2016-01-01", "2026-01-01"]),
        "shares_outstanding": [80.0, 100.0, 200.0],
    })

    result = fundamental_growth_over_years(
        snapshots,
        value_column="shares_outstanding",
        as_of=pd.Timestamp("2026-01-01"),
        years=10,
    )

    assert result is not None
    assert result["full_period"] is True
    assert result["start_date"] == "2016-01-01"
    assert result["total_growth_pct"] == 100.0
    assert result["cagr_pct"] == pytest.approx(7.1773, rel=1e-3)


def test_fundamental_growth_labels_shorter_available_history():
    snapshots = pd.DataFrame({
        "effective_date": pd.to_datetime(["2020-01-01", "2026-01-01"]),
        "shares_outstanding": [100.0, 150.0],
    })

    result = fundamental_growth_over_years(
        snapshots,
        value_column="shares_outstanding",
        as_of=pd.Timestamp("2026-01-01"),
        years=10,
    )

    assert result is not None
    assert result["full_period"] is False
    assert result["observed_years"] == pytest.approx(6.0, rel=1e-3)
    assert result["total_growth_pct"] == 50.0


def test_point_in_time_fundamental_carries_forward_only_after_publication():
    dates = pd.to_datetime(["2026-01-02", "2026-01-05", "2026-01-06", "2026-04-06"])
    snapshots = pd.DataFrame({
        "effective_date": pd.to_datetime(["2026-01-05", "2026-04-06"]),
        "eps_ttm": [4.0, 5.0],
    })

    result = point_in_time_fundamental(
        dates, snapshots, value_column="eps_ttm", name="eps_ttm"
    )

    assert pd.isna(result.iloc[0])
    assert result.iloc[1:].tolist() == [4.0, 4.0, 5.0]


def test_point_in_time_trailing_pe_uses_only_effective_snapshots():
    dates = pd.to_datetime(["2026-01-02", "2026-01-05", "2026-01-06", "2026-01-07"])
    close = pd.Series([100.0, 102.0, 104.0, 108.0], index=dates)
    snapshots = pd.DataFrame({
        "effective_date": pd.to_datetime(["2026-01-05", "2026-01-07"]),
        "eps_ttm": [4.0, 6.0],
    })

    result = point_in_time_trailing_pe(close, snapshots)

    assert pd.isna(result.iloc[0])
    assert result.iloc[1] == 25.5
    assert result.iloc[2] == 26.0
    assert result.iloc[3] == 18.0


def test_point_in_time_trailing_pe_applies_price_unit_and_ignores_losses():
    dates = pd.to_datetime(["2026-01-05", "2026-01-06"])
    close = pd.Series([120.0, 121.0], index=dates)
    snapshots = pd.DataFrame({
        "effective_date": pd.to_datetime(["2026-01-05", "2026-01-06"]),
        "eps_ttm": [6000.0, -100.0],
    })

    result = point_in_time_trailing_pe(close, snapshots, price_multiplier=1000.0)

    assert result.iloc[0] == 20.0
    assert result.iloc[1] == 121000.0 / 6000.0


def test_rebase_eps_uses_provider_pe_on_adjusted_price_basis():
    close = pd.Series(
        [15.0, 16.0],
        index=pd.to_datetime(["2018-03-29", "2018-04-02"]),
    )
    snapshots = pd.DataFrame({
        "period_end": pd.to_datetime(["2018-03-31"]),
        "reported_pe": [7.5],
        "eps_ttm": [5000.0],
    })

    rebased = rebase_eps_to_adjusted_prices(
        close, snapshots, price_multiplier=1000.0
    )

    assert rebased.iloc[0]["eps_ttm"] == 2000.0
