"""Tests for trading_engine/factor_analysis/ — Layer 3 validation gate.

Gate: from trading_engine.factor_analysis import analyze_cross_section, detect_regime
"""
from __future__ import annotations

import pandas as pd
import pytest

from trading_engine.factor_analysis import (
    analyze_cross_section,
    detect_regime,
    percentile_breakdown,
    rarity_analysis,
)
from trading_engine.factors import MovingAverageRatio
from trading_engine.types import (
    FactorSeries,
    InsufficientDataError,
)

from tests.trading_engine.conftest import make_price_frame


# =============================================================================
# [L] Time-series analysis
# =============================================================================

class TestPercentileBreakdown:
    def _factor(self, values: list[float]) -> FactorSeries:
        return FactorSeries(
            name="test_factor",
            values=pd.Series(values, index=pd.date_range("2020-01-01", periods=len(values))),
        )

    def test_basic_percentiles(self):
        # 100 values from 1 to 100
        factor = self._factor(list(range(1, 101)))
        result = percentile_breakdown(factor, buckets=[10, 50, 90])
        assert result.percentiles[50] == pytest.approx(50.5, abs=1.0)
        assert result.percentiles[10] < result.percentiles[50]
        assert result.percentiles[90] > result.percentiles[50]

    def test_current_percentile_in_range(self, price_frame):
        factor = MovingAverageRatio(length=20).compute(price_frame)
        result = percentile_breakdown(factor)
        assert 0.0 <= result.current_percentile <= 100.0

    def test_history_length_matches(self):
        factor = self._factor(list(range(1, 201)))
        result = percentile_breakdown(factor)
        assert result.history_length_days == 200

    def test_insufficient_data_raises(self):
        factor = self._factor([1.0])  # only 1 value
        with pytest.raises(InsufficientDataError):
            percentile_breakdown(factor)

    def test_default_buckets(self):
        factor = self._factor(list(range(1, 101)))
        result = percentile_breakdown(factor)
        # Default buckets should include 50
        assert 50 in result.percentiles


class TestRarityAnalysis:
    def test_focuses_on_tails(self):
        """rarity_analysis should use fine-grained low-percentile buckets."""
        factor = FactorSeries(
            name="test",
            values=pd.Series(range(1, 101), index=pd.date_range("2020-01-01", periods=100)),
        )
        result = rarity_analysis(factor)
        # Should have low-end percentiles
        assert 1 in result.percentiles
        assert 5 in result.percentiles


# =============================================================================
# [O] Cross-sectional analysis + detect_regime
# =============================================================================

class TestAnalyzeCrossSection:
    def test_basic_output(self, prices_dict):
        factor = MovingAverageRatio(length=20)
        result = analyze_cross_section(
            factor=factor,
            universe=list(prices_dict.keys()),
            prices=prices_dict,
            threshold=0.0,
        )
        assert not result.breadth.empty
        assert (result.breadth >= 0.0).all()
        assert (result.breadth <= 1.0).all()

    def test_pct_above_matches_counts(self, prices_dict):
        factor = MovingAverageRatio(length=20)
        result = analyze_cross_section(
            factor=factor,
            universe=list(prices_dict.keys()),
            prices=prices_dict,
            threshold=0.0,
        )
        # pct_above should equal counts_above / n_symbols * 100
        n = len(prices_dict)
        expected = result.counts_above / n * 100
        pd.testing.assert_series_equal(
            result.pct_above, expected, check_names=False, atol=1e-6
        )

    def test_empty_universe_raises(self, prices_dict):
        factor = MovingAverageRatio(length=20)
        with pytest.raises(ValueError, match="Universe cannot be empty"):
            analyze_cross_section(factor=factor, universe=[], prices=prices_dict)

    def test_ranks_shape(self, prices_dict):
        factor = MovingAverageRatio(length=20)
        result = analyze_cross_section(
            factor=factor,
            universe=list(prices_dict.keys()),
            prices=prices_dict,
        )
        # Ranks should be (time x symbols)
        assert result.ranks.shape[1] == len(prices_dict)

    def test_threshold_none_defaults_to_zero(self, prices_dict):
        factor = MovingAverageRatio(length=20)
        result_none = analyze_cross_section(factor, list(prices_dict.keys()), prices_dict, threshold=None)
        result_zero = analyze_cross_section(factor, list(prices_dict.keys()), prices_dict, threshold=0.0)
        pd.testing.assert_series_equal(result_none.breadth, result_zero.breadth)


class TestDetectRegime:
    def _breadth(self, values: list[float]) -> pd.Series:
        return pd.Series(
            values, index=pd.date_range("2020-01-01", periods=len(values))
        )

    def test_labels_correctly(self):
        breadth = self._breadth([0.1, 0.5, 0.9, 0.2, 0.8])
        result = detect_regime(breadth, thresholds=(0.3, 0.7))
        assert result.labels.iloc[0] == "risk_off"   # 0.1 < 0.3
        assert result.labels.iloc[1] == "transition"  # 0.3 <= 0.5 <= 0.7
        assert result.labels.iloc[2] == "risk_on"     # 0.9 > 0.7
        assert result.labels.iloc[3] == "risk_off"   # 0.2 < 0.3
        assert result.labels.iloc[4] == "risk_on"    # 0.8 > 0.7

    def test_only_three_labels(self):
        breadth = self._breadth([x / 10 for x in range(11)])
        result = detect_regime(breadth, thresholds=(0.3, 0.7))
        valid = {"risk_on", "risk_off", "transition"}
        assert set(result.labels.unique()).issubset(valid)

    def test_invalid_thresholds_raises(self):
        breadth = self._breadth([0.5])
        with pytest.raises(ValueError, match="Lower threshold"):
            detect_regime(breadth, thresholds=(0.8, 0.3))

    def test_out_of_range_thresholds_raises(self):
        breadth = self._breadth([0.5])
        with pytest.raises(ValueError, match="in \\[0, 1\\]"):
            detect_regime(breadth, thresholds=(-0.1, 1.5))

    def test_empty_series_raises(self):
        with pytest.raises(InsufficientDataError):
            detect_regime(pd.Series(dtype=float), thresholds=(0.3, 0.7))
