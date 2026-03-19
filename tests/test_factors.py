"""Unit tests for src/factors/*.

Each factor's calculate() method is tested against a synthetic price DataFrame
so that off-by-one errors, wrong window alignment, or bad denominators produce
an immediate, reproducible failure — not a silent wrong number on the UI.
"""
import numpy as np
import pandas as pd
import pytest

from src.factors.distance_from_peak import DistanceFromPeakFactor
from src.factors.ma_ratio import MARatioFactor
from src.factors.ahr999 import AHR999Factor


def _make_price_df(closes: list[float], start: str = "2020-01-01") -> pd.DataFrame:
    idx = pd.bdate_range(start, periods=len(closes))
    return pd.DataFrame({"Close": closes, "Open": closes, "High": closes, "Low": closes}, index=idx)


def _make_btc_price_df(n: int = 300) -> pd.DataFrame:
    """Synthetic BTC-USD price series long enough for the 200-bar MA warmup."""
    idx = pd.bdate_range("2015-01-01", periods=n)
    closes = [10_000 * (1 + 0.001 * i) for i in range(n)]
    return pd.DataFrame({"Close": closes}, index=idx)


# ---------------------------------------------------------------------------
# DistanceFromPeakFactor
# ---------------------------------------------------------------------------

class TestDistanceFromPeakFactor:
    def test_at_peak_value_is_zero(self):
        """When price equals the rolling peak, factor = 0."""
        closes = [100, 110, 120, 120, 120]  # peak at 120
        df = _make_price_df(closes)
        factor = DistanceFromPeakFactor(window_days=3)
        series = factor.calculate(df)

        # Last bar: price=120, rolling(3).max()=120 → distance = 0
        assert series.iloc[-1] == pytest.approx(0.0)

    def test_below_peak_is_negative(self):
        """When price is below the rolling peak, factor is negative."""
        closes = [100, 120, 100]  # peak 120, current 100 → -16.67%
        df = _make_price_df(closes)
        factor = DistanceFromPeakFactor(window_days=3)
        series = factor.calculate(df)

        expected = 100 / 120 - 1  # ≈ -0.1667
        assert series.iloc[-1] == pytest.approx(expected, rel=1e-4)

    def test_monotonically_increasing_always_zero(self):
        """Rising prices always equal the rolling peak → all values 0."""
        closes = [100, 110, 120, 130, 140]
        df = _make_price_df(closes)
        factor = DistanceFromPeakFactor(window_days=3)
        series = factor.calculate(df)

        assert np.allclose(series.values, 0.0, atol=1e-10)

    def test_output_length_after_dropna(self):
        """Series length = len(price) - window + 1 after dropna."""
        closes = list(range(100, 115))  # 15 bars
        window = 5
        df = _make_price_df(closes)
        factor = DistanceFromPeakFactor(window_days=window)
        series = factor.calculate(df)

        assert len(series) == len(closes) - window + 1

    def test_name_includes_window(self):
        factor = DistanceFromPeakFactor(window_days=200)
        assert "200" in factor.name

    def test_known_drawdown(self):
        """Peak of 200, then drops to 100 → distance = -0.5."""
        closes = [100, 200, 150, 100]
        df = _make_price_df(closes)
        factor = DistanceFromPeakFactor(window_days=4)
        series = factor.calculate(df)

        assert series.iloc[-1] == pytest.approx(-0.5, rel=1e-4)


# ---------------------------------------------------------------------------
# MARatioFactor
# ---------------------------------------------------------------------------

class TestMARatioFactor:
    def test_flat_price_sma_ratio_is_zero(self):
        """When price is flat, price/SMA = 1 → ratio = 0."""
        closes = [100.0] * 20
        df = _make_price_df(closes)
        factor = MARatioFactor("SMA", 10)
        series = factor.calculate(df)

        assert np.allclose(series.values, 0.0, atol=1e-10)

    def test_above_ma_is_positive(self):
        """When current price is above the MA, ratio > 0."""
        # Start low, spike up so the last price is well above the MA
        closes = [100.0] * 19 + [200.0]
        df = _make_price_df(closes)
        factor = MARatioFactor("SMA", 10)
        series = factor.calculate(df)

        assert series.iloc[-1] > 0

    def test_below_ma_is_negative(self):
        """When current price is below the MA, ratio < 0."""
        closes = [100.0] * 19 + [50.0]
        df = _make_price_df(closes)
        factor = MARatioFactor("SMA", 10)
        series = factor.calculate(df)

        assert series.iloc[-1] < 0

    def test_ema_type_accepted(self):
        """EMA type does not raise."""
        closes = [100.0 + i for i in range(30)]
        df = _make_price_df(closes)
        factor = MARatioFactor("EMA", 10)
        series = factor.calculate(df)
        assert len(series) > 0

    def test_wma_type_accepted(self):
        """WMA type does not raise."""
        closes = [100.0 + i for i in range(30)]
        df = _make_price_df(closes)
        factor = MARatioFactor("WMA", 10)
        series = factor.calculate(df)
        assert len(series) > 0

    def test_name_includes_type_and_length(self):
        factor = MARatioFactor("EMA", 50)
        assert "EMA" in factor.name
        assert "50" in factor.name

    def test_known_value(self):
        """SMA(3) of [100, 100, 150] = 116.67 → ratio = 150/116.67 - 1 ≈ 0.2857."""
        closes = [100.0, 100.0, 150.0]
        df = _make_price_df(closes)
        factor = MARatioFactor("SMA", 3)
        series = factor.calculate(df)

        expected = 150.0 / (350.0 / 3) - 1
        assert series.iloc[-1] == pytest.approx(expected, rel=1e-4)


# ---------------------------------------------------------------------------
# AHR999Factor
# ---------------------------------------------------------------------------

class TestAHR999Factor:
    def test_returns_series(self):
        """AHR999 factor returns a non-empty Series on sufficient data."""
        df = _make_btc_price_df(n=300)
        factor = AHR999Factor()
        series = factor.calculate(df)

        assert isinstance(series, pd.Series)
        assert len(series) > 0

    def test_all_values_positive(self):
        """AHR999 is defined as a product of two positive ratios → always > 0."""
        df = _make_btc_price_df(n=300)
        factor = AHR999Factor()
        series = factor.calculate(df)

        assert (series > 0).all()

    def test_requires_200_bar_warmup(self):
        """Series is shorter than the 200-bar warmup due to MA NaN drop."""
        df = _make_btc_price_df(n=300)
        factor = AHR999Factor()
        series = factor.calculate(df)

        assert len(series) < 300

    def test_is_applicable_only_for_btc(self):
        """AHR999 should only apply to BTC-USD."""
        factor = AHR999Factor()
        assert factor.is_applicable("BTC-USD") is True
        assert factor.is_applicable("ETH-USD") is False
        assert factor.is_applicable("VCB") is False

    def test_name(self):
        assert AHR999Factor().name == "AHR999"
