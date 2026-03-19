"""Tests for trading_engine/factors/ — Layer 2 validation gate.

Gate: from trading_engine.factors import MovingAverageRatio
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from trading_engine.factors import (
    AHR999,
    BollingerBands,
    DonchianChannel,
    DistanceFromPeak,
    MovingAverage,
    MovingAverageRatio,
)
from trading_engine.factors.moving_average import compute_ma
from trading_engine.types import FactorComputeError, FactorSeries, PriceFrame

from tests.trading_engine.conftest import make_price_frame


# =============================================================================
# [F] compute_ma utility
# =============================================================================

class TestComputeMA:
    def _series(self, values: list[float]) -> pd.Series:
        return pd.Series(values, index=pd.date_range("2020-01-01", periods=len(values)))

    def test_sma_simple(self):
        s = self._series([1.0, 2.0, 3.0, 4.0, 5.0])
        result = compute_ma(s, "SMA", 3)
        # SMA(3) at index 2 = (1+2+3)/3 = 2.0
        assert result.iloc[2] == pytest.approx(2.0)

    def test_ema_converges(self):
        s = self._series([10.0] * 100)
        result = compute_ma(s, "EMA", 20)
        assert result.dropna().iloc[-1] == pytest.approx(10.0, abs=1e-6)

    def test_wma_weights_sum_to_one(self):
        """WMA with uniform prices should equal the price."""
        s = self._series([5.0] * 50)
        result = compute_ma(s, "WMA", 10)
        assert result.dropna().iloc[-1] == pytest.approx(5.0)

    def test_invalid_ma_type_raises(self):
        s = self._series([1.0, 2.0])
        with pytest.raises(FactorComputeError, match="Unknown MA type"):
            compute_ma(s, "INVALID", 2)  # type: ignore

    def test_length_zero_raises(self):
        s = self._series([1.0, 2.0])
        with pytest.raises(FactorComputeError):
            compute_ma(s, "SMA", 0)


# =============================================================================
# [G] MovingAverageRatio
# =============================================================================

class TestMovingAverageRatio:
    def test_output_name(self, price_frame):
        factor = MovingAverageRatio(ma_type="SMA", length=20)
        result = factor.compute(price_frame)
        assert "SMA" in result.name
        assert "20" in result.name

    def test_values_are_series(self, price_frame):
        factor = MovingAverageRatio(length=20)
        result = factor.compute(price_frame)
        assert isinstance(result.values, pd.Series)
        assert not result.values.empty

    def test_no_nan_in_output(self, price_frame):
        factor = MovingAverageRatio(length=20)
        result = factor.compute(price_frame)
        assert not result.values.isna().any()

    def test_zero_price_raises(self):
        """Factor should raise FactorComputeError when MA contains zeros."""
        df = pd.DataFrame(
            {"open": [0.0]*50, "high": [0.0]*50, "low": [0.0]*50, "close": [0.0]*50},
            index=pd.date_range("2020-01-01", periods=50),
        )
        pf = PriceFrame(symbol="ZERO", data=df, source="test")
        factor = MovingAverageRatio(length=20)
        with pytest.raises(FactorComputeError):
            factor.compute(pf)

    def test_insufficient_data_raises(self):
        pf = make_price_frame("X", days=10)
        factor = MovingAverageRatio(length=50)
        with pytest.raises(FactorComputeError, match="Need at least"):
            factor.compute(pf)

    def test_metadata_populated(self, price_frame):
        factor = MovingAverageRatio(ma_type="EMA", length=30)
        result = factor.compute(price_frame)
        assert result.metadata["ma_type"] == "EMA"
        assert result.metadata["length"] == 30


# =============================================================================
# [H] BollingerBands, DonchianChannel, DistanceFromPeak, AHR999
# =============================================================================

class TestBollingerBands:
    def test_basic_compute(self, price_frame):
        factor = BollingerBands(period=20, num_std=2.0)
        result = factor.compute(price_frame)
        assert isinstance(result.values, pd.Series)
        assert not result.values.empty

    def test_constant_price_raises(self):
        """Zero band width (constant prices) should raise."""
        df = pd.DataFrame(
            {"open": [100.0]*30, "high": [100.0]*30, "low": [100.0]*30, "close": [100.0]*30},
            index=pd.date_range("2020-01-01", periods=30),
        )
        pf = PriceFrame(symbol="FLAT", data=df, source="test")
        factor = BollingerBands(period=20)
        with pytest.raises(FactorComputeError):
            factor.compute(pf)

    def test_compute_bands_returns_three_series(self, price_frame):
        factor = BollingerBands(period=20)
        sma, upper, lower = factor.compute_bands(price_frame)
        # Align on common non-NaN index before comparing
        common = sma.dropna().index.intersection(upper.dropna().index).intersection(lower.dropna().index)
        assert (upper.loc[common] >= sma.loc[common]).all()
        assert (sma.loc[common] >= lower.loc[common]).all()


class TestDonchianChannel:
    def test_basic_compute(self, price_frame):
        factor = DonchianChannel(entry_length=20, exit_length=10)
        result = factor.compute(price_frame)
        assert isinstance(result.values, pd.Series)
        assert not result.values.empty

    def test_compute_channels(self, price_frame):
        factor = DonchianChannel(entry_length=20, exit_length=10)
        upper, lower = factor.compute_channels(price_frame)
        # Align on common non-NaN index before comparing
        common = upper.dropna().index.intersection(lower.dropna().index)
        assert (upper.loc[common] >= lower.loc[common]).all()


class TestDistanceFromPeak:
    def test_output_in_range(self, price_frame):
        factor = DistanceFromPeak(window=50)
        result = factor.compute(price_frame)
        # Distance from peak is in (-1, 0]
        assert (result.values <= 0.0).all()
        assert (result.values >= -1.0).all()

    def test_at_new_high_is_zero(self):
        """When price is monotonically increasing, distance = 0."""
        prices = np.linspace(100, 200, 100)
        df = pd.DataFrame(
            {"open": prices, "high": prices, "low": prices, "close": prices},
            index=pd.date_range("2020-01-01", periods=100),
        )
        pf = PriceFrame(symbol="UP", data=df, source="test")
        factor = DistanceFromPeak(window=20)
        result = factor.compute(pf)
        assert result.values.max() == pytest.approx(0.0)


class TestAHR999:
    def test_basic_compute(self, price_frame):
        factor = AHR999()
        result = factor.compute(price_frame)
        assert isinstance(result.values, pd.Series)
        assert not result.values.empty
        assert result.name == "AHR999"

    def test_insufficient_data_raises(self):
        pf = make_price_frame("BTC", days=100)
        factor = AHR999()
        with pytest.raises(FactorComputeError, match="Need at least 200"):
            factor.compute(pf)
