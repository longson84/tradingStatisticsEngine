"""Tests for the cross-sectional market health indicator."""
from __future__ import annotations

import pandas as pd
import pytest

from trading_engine.factor_analysis.market_health import (
    classify_market_health,
    compute_market_distance_snapshot,
    compute_market_health,
)
from trading_engine.types import MarketHealthWeights, PriceFrame


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


def test_market_health_combines_equal_weight_breadth_components():
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
    assert current["within_10"] == pytest.approx(50.0)
    assert current["within_20"] == pytest.approx(50.0)
    assert current["within_30"] == pytest.approx(50.0)
    assert current["stress_40"] == pytest.approx(50.0)
    assert current["health_score"] == pytest.approx(50.0)
    assert current["coverage_pct"] == pytest.approx(100.0)


def test_custom_weights_are_normalized_to_a_zero_to_100_score():
    dates = pd.date_range("2024-01-01", periods=205, freq="B")
    prices = {
        "AT_HIGH": _prices("AT_HIGH", [100.0] * 205, dates),
        "DOWN_15": _prices("DOWN_15", [100.0] * 204 + [85.0], dates),
    }

    result = compute_market_health(
        prices,
        universe="TEST",
        weights=MarketHealthWeights(
            within_10=2.0,
            within_20=0.0,
            within_30=0.0,
            not_below_40=0.0,
        ),
        window=200,
        minimum_coverage=1.0,
    )

    assert result.series.iloc[-1]["health_score"] == pytest.approx(50.0)


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
        before.series["health_score"].iloc[:-1],
        after.series["health_score"].iloc[:-1],
    )
    assert before.series["health_score"].iloc[-1] == pytest.approx(100.0)
    assert after.series["health_score"].iloc[-1] == pytest.approx(0.0)


def test_regime_classification_combines_level_and_direction():
    assert classify_market_health(72.0, 5.0) == "strong_improving"
    assert classify_market_health(32.0, -4.0) == "weak_deteriorating"
    assert classify_market_health(51.0, 1.0) == "mixed_stable"
