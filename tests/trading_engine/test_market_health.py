"""Tests for the cross-sectional market health indicator."""
from __future__ import annotations

import pandas as pd
import pytest

from trading_engine.factor_analysis.market_health import (
    compute_market_distance_snapshot,
    compute_market_health,
    compute_market_health_from_closes,
)
from trading_engine.types import PriceFrame


def _prices(symbol: str, close: list[float], dates: pd.DatetimeIndex) -> PriceFrame:
    values = pd.Series(close, index=dates, dtype=float)
    return PriceFrame(
        symbol=symbol,
        data=pd.DataFrame(
            {
                "open": values,
                "high": values,
                "low": values,
                "close": values,
                "volume": 1_000_000.0,
            }
        ),
        source="synthetic",
    )


def test_market_health_reports_cross_sectional_median_distance():
    dates = pd.date_range("2024-01-01", periods=205, freq="B")
    prices = {
        "AT_HIGH": _prices("AT_HIGH", [100.0] * 205, dates),
        "HALVED": _prices("HALVED", [100.0] * 204 + [50.0], dates),
    }

    result = compute_market_health(
        prices,
        universe="TEST",
        window=200,
        minimum_coverage=1.0,
    )
    current = result.series.iloc[-1]

    assert current["median_distance"] == pytest.approx(-25.0)
    assert current["coverage_pct"] == pytest.approx(100.0)
    assert current["eligible_count"] == 2
    assert list(result.series.columns) == [
        "median_distance",
        "coverage_pct",
        "eligible_count",
    ]


def test_market_health_carries_forward_a_missing_trading_session():
    dates = pd.date_range("2024-01-01", periods=205, freq="B")
    incomplete = [100.0] * 205
    incomplete[-2] = float("nan")
    prices = {
        "AT_HIGH": _prices("AT_HIGH", [100.0] * 205, dates),
        "INCOMPLETE": _prices("INCOMPLETE", incomplete, dates),
    }

    result = compute_market_health(
        prices,
        universe="TEST",
        window=200,
        minimum_coverage=1.0,
    )

    assert result.series.index[-1] == dates[-1]
    assert dates[-2] in result.series.index
    assert (result.series["eligible_count"] == 2).all()


def test_distance_snapshot_carries_forward_a_missing_session():
    dates = pd.date_range("2024-01-01", periods=205, freq="B")
    incomplete_dates = dates.delete(-1)
    prices = {
        "ACTIVE": _prices("ACTIVE", [100.0] * 205, dates),
        "NO_TRADE": _prices(
            "NO_TRADE",
            [100.0] * 203 + [80.0],
            incomplete_dates,
        ),
    }

    rows = compute_market_distance_snapshot(
        prices,
        as_of=dates[-1].date(),
        window=200,
    )

    by_symbol = {row.symbol: row for row in rows}
    assert by_symbol["NO_TRADE"].current_price == 80.0
    assert by_symbol["NO_TRADE"].distance == pytest.approx(-20.0)


def test_close_matrix_path_matches_price_frame_path():
    dates = pd.date_range("2024-01-01", periods=205, freq="B")
    prices = {
        "A": _prices("A", [100.0] * 205, dates),
        "B": _prices("B", [100.0] * 204 + [75.0], dates),
    }
    closes = pd.concat(
        {symbol: frame.data["close"] for symbol, frame in prices.items()}, axis=1
    )

    from_frames = compute_market_health(
        prices, universe="TEST", window=200, minimum_coverage=1.0
    )
    from_matrix = compute_market_health_from_closes(
        closes, universe="TEST", window=200, minimum_coverage=1.0
    )

    pd.testing.assert_frame_equal(from_frames.series, from_matrix.series)
    assert from_frames.distribution == from_matrix.distribution


def test_current_distribution_counts_non_overlapping_distance_bands():
    dates = pd.date_range("2024-01-01", periods=205, freq="B")
    final_prices = [100.0, 95.0, 85.0, 75.0, 65.0, 55.0, 45.0, 35.0, 25.0, 15.0, 5.0]
    prices = {
        f"S{index}": _prices(
            f"S{index}",
            [100.0] * 204 + [final_price],
            dates,
        )
        for index, final_price in enumerate(final_prices)
    }

    result = compute_market_health(
        prices,
        universe="TEST",
        window=200,
        minimum_coverage=1.0,
    )

    assert [bucket.label for bucket in result.distribution] == [
        "0 to -10%",
        "-10 to -20%",
        "-20 to -30%",
        "-30 to -40%",
        "-40 to -50%",
        "-50 to -60%",
        "-60 to -70%",
        "-70 to -80%",
        "-80 to -90%",
        "-90 to -100%",
    ]
    assert [bucket.count for bucket in result.distribution] == [2, 1, 1, 1, 1, 1, 1, 1, 1, 1]
    assert sum(bucket.percentage for bucket in result.distribution) == pytest.approx(100.0)
    assert result.distribution[0].percentage == pytest.approx(2 / 11 * 100)
    assert result.distribution[0].cumulative_percentage == pytest.approx(2 / 11 * 100)
    assert result.distribution[-1].cumulative_percentage == pytest.approx(100.0)


def test_distance_snapshot_returns_exact_bucket_members():
    dates = pd.date_range("2024-01-01", periods=205, freq="B")
    prices = {
        "DOWN_15": _prices("DOWN_15", [100.0] * 204 + [85.0], dates),
        "DOWN_25": _prices("DOWN_25", [100.0] * 204 + [75.0], dates),
    }

    rows = compute_market_distance_snapshot(
        prices,
        as_of=dates[-1].date(),
        window=200,
        min_distance=-20.0,
        max_distance=-10.0,
    )

    assert [row.symbol for row in rows] == ["DOWN_15"]
    assert rows[0].current_price == 85.0
    assert rows[0].rolling_high == 100.0
    assert rows[0].distance == pytest.approx(-15.0)


def test_market_health_does_not_look_ahead():
    dates = pd.date_range("2024-01-01", periods=220, freq="B")
    base = [100.0] * 220
    changed_future = base.copy()
    changed_future[-1] = 20.0

    before = compute_market_health(
        {"A": _prices("A", base, dates)},
        universe="TEST",
        window=200,
        minimum_coverage=1.0,
    )
    after = compute_market_health(
        {"A": _prices("A", changed_future, dates)},
        universe="TEST",
        window=200,
        minimum_coverage=1.0,
    )

    pd.testing.assert_series_equal(
        before.series["median_distance"].iloc[:-1],
        after.series["median_distance"].iloc[:-1],
    )
    assert before.series["median_distance"].iloc[-1] == pytest.approx(0.0)
    assert after.series["median_distance"].iloc[-1] == pytest.approx(-80.0)
