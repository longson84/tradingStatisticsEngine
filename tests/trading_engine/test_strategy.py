"""Tests for trading_engine/strategy/ — Layer 4 validation gate.

Gate: from trading_engine.strategy import MACrossover
Key verifications:
- Zero-crossing atomic rule: weight 0.5 -> -0.3 = exactly 2 Trade records
- Weight NaN -> StrategyOutputError
- BaseStrategy auto-clamp to [-1, 1]
- EnsembleStrategy = weighted average of sub-strategies
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from trading_engine.strategy import BuyAndHold, EnsembleStrategy, MACrossover
from trading_engine.strategy.base import BaseStrategy
from trading_engine.strategy.utils import weight_transitions_to_trades
from trading_engine.types import (
    PriceFrame,
    RegimeSeries,
    StrategyOutput,
    StrategyOutputError,
    Trade,
)

from tests.trading_engine.conftest import make_price_frame


# =============================================================================
# [R] weight_transitions_to_trades — zero-crossing rule
# =============================================================================

class TestWeightTransitionsToTrades:
    def _make_prices(self, n: int = 10, start_price: float = 100.0) -> dict[str, PriceFrame]:
        prices = np.linspace(start_price, start_price * 1.1, n)
        df = pd.DataFrame(
            {"open": prices, "high": prices * 1.01, "low": prices * 0.99, "close": prices},
            index=pd.date_range("2020-01-01", periods=n, freq="B"),
        )
        return {"SYM": PriceFrame(symbol="SYM", data=df, source="test")}

    def _make_weights(self, values: list[float], n: int = None) -> pd.DataFrame:
        n = n or len(values)
        idx = pd.date_range("2020-01-01", periods=n, freq="B")
        return pd.DataFrame({"SYM": values}, index=idx)

    def test_flat_to_long_creates_one_trade(self):
        prices = self._make_prices(10)
        weights = self._make_weights([0, 0, 0, 1, 1, 1, 1, 0, 0, 0])
        trades = weight_transitions_to_trades(weights, prices)
        assert len(trades) == 1
        assert trades[0].direction == "long"

    def test_zero_crossing_creates_two_trades_atomically(self):
        """weight 0.5 -> -0.3 must create 2 Trade records in the same bar."""
        prices = self._make_prices(10)
        # Long for 3 bars, then cross to short in bar 4, stay short
        weights = self._make_weights([0, 1, 1, 1, -1, -1, -1, 0, 0, 0])
        trades = weight_transitions_to_trades(weights, prices)
        # Should have: 1 long trade (exit at bar 4) + 1 short trade (enter at bar 4)
        assert len(trades) == 2
        long_trades = [t for t in trades if t.direction == "long"]
        short_trades = [t for t in trades if t.direction == "short"]
        assert len(long_trades) == 1
        assert len(short_trades) == 1
        # Both events happen at the same bar
        assert long_trades[0].exit_date == short_trades[0].entry_date

    def test_partial_weight_appends_weight_history(self):
        """0.5 -> 0.3 (same direction) = one trade with 2 WeightEvents."""
        prices = self._make_prices(10)
        weights = self._make_weights([0, 0.5, 0.5, 0.3, 0.3, 0, 0, 0, 0, 0])
        trades = weight_transitions_to_trades(weights, prices)
        assert len(trades) == 1
        assert len(trades[0].weight_history) == 2  # entry + scale down

    def test_nan_weights_raises(self):
        prices = self._make_prices(5)
        weights = self._make_weights([0, 1, float("nan"), 0, 0])
        with pytest.raises(StrategyOutputError, match="NaN"):
            weight_transitions_to_trades(weights, prices)

    def test_trade_has_return_pct(self):
        prices = self._make_prices(10)
        weights = self._make_weights([0, 0, 1, 1, 1, 0, 0, 0, 0, 0])
        trades = weight_transitions_to_trades(weights, prices)
        assert trades[0].return_pct is not None

    def test_trade_has_mae_and_mfe(self):
        prices = self._make_prices(10)
        weights = self._make_weights([0, 0, 1, 1, 1, 1, 0, 0, 0, 0])
        trades = weight_transitions_to_trades(weights, prices)
        assert trades[0].mae_pct is not None
        assert trades[0].mfe_pct is not None

    def test_open_trade_emitted_at_end(self):
        """A trade still open at the last bar should still be emitted."""
        prices = self._make_prices(10)
        weights = self._make_weights([0, 0, 1, 1, 1, 1, 1, 1, 1, 1])
        trades = weight_transitions_to_trades(weights, prices)
        assert len(trades) == 1
        assert trades[0].exit_date is not None  # emitted at last bar


# =============================================================================
# [V] BaseStrategy NaN validation + clamping
# =============================================================================

class _NaNStrategy(BaseStrategy):
    """Strategy that deliberately outputs NaN — for testing validation."""
    def _compute_weights(self, symbols, prices, regime=None) -> pd.DataFrame:
        idx = prices[symbols[0]].data.index
        df = pd.DataFrame({s: [float("nan")] * len(idx) for s in symbols}, index=idx)
        return df


class _OverWeightStrategy(BaseStrategy):
    """Strategy that outputs weights > 1 — should be clamped."""
    def _compute_weights(self, symbols, prices, regime=None) -> pd.DataFrame:
        idx = prices[symbols[0]].data.index
        df = pd.DataFrame({s: [2.0] * len(idx) for s in symbols}, index=idx)
        return df


class TestBaseStrategy:
    def test_nan_raises_strategy_output_error(self, prices_dict):
        strategy = _NaNStrategy()
        with pytest.raises(StrategyOutputError, match="NaN"):
            strategy.compute(list(prices_dict.keys()), prices_dict)

    def test_weights_clamped_to_minus_one_plus_one(self, prices_dict):
        strategy = _OverWeightStrategy()
        output = strategy.compute(list(prices_dict.keys()), prices_dict)
        assert output.weights.max().max() <= 1.0
        assert output.weights.min().min() >= -1.0


# =============================================================================
# [W] Strategy implementations
# =============================================================================

class TestMACrossover:
    def test_weights_are_binary(self, prices_dict):
        """MACrossover should only produce 0.0 or 1.0 weights."""
        strategy = MACrossover(fast_length=10, slow_length=50)
        output = strategy.compute(list(prices_dict.keys()), prices_dict)
        unique_values = set(output.weights.values.flatten())
        assert unique_values.issubset({0.0, 1.0})

    def test_output_has_correct_columns(self, prices_dict):
        strategy = MACrossover()
        output = strategy.compute(list(prices_dict.keys()), prices_dict)
        assert set(output.weights.columns) == set(prices_dict.keys())

    def test_trades_are_long_only(self, prices_dict):
        strategy = MACrossover()
        output = strategy.compute(list(prices_dict.keys()), prices_dict)
        for trade in output.trades:
            assert trade.direction == "long"


class TestBuyAndHold:
    def test_all_weights_equal_one(self, prices_dict):
        strategy = BuyAndHold(weight=1.0)
        output = strategy.compute(list(prices_dict.keys()), prices_dict)
        assert (output.weights == 1.0).all().all()

    def test_custom_weight(self, prices_dict):
        strategy = BuyAndHold(weight=0.5)
        output = strategy.compute(list(prices_dict.keys()), prices_dict)
        assert (output.weights == 0.5).all().all()


class TestEnsembleStrategy:
    def test_equal_weight_is_average(self, prices_dict):
        """EnsembleStrategy with equal weights = average of sub-strategy weights."""
        s1 = BuyAndHold(weight=1.0)
        s2 = BuyAndHold(weight=0.0)
        ensemble = EnsembleStrategy([s1, s2])
        output = ensemble.compute(list(prices_dict.keys()), prices_dict)
        # Average of 1.0 and 0.0 = 0.5
        assert output.weights.mean().mean() == pytest.approx(0.5)

    def test_custom_weights_applied(self, prices_dict):
        s1 = BuyAndHold(weight=1.0)
        s2 = BuyAndHold(weight=0.0)
        ensemble = EnsembleStrategy([s1, s2], strategy_weights=[0.8, 0.2])
        output = ensemble.compute(list(prices_dict.keys()), prices_dict)
        assert output.weights.mean().mean() == pytest.approx(0.8)

    def test_weights_normalized(self, prices_dict):
        """strategy_weights should be normalized to sum to 1."""
        s1 = BuyAndHold(weight=1.0)
        s2 = BuyAndHold(weight=1.0)
        ensemble = EnsembleStrategy([s1, s2], strategy_weights=[2.0, 2.0])
        output = ensemble.compute(list(prices_dict.keys()), prices_dict)
        # Both equal -> average = 1.0
        assert output.weights.mean().mean() == pytest.approx(1.0)

    def test_empty_strategies_raises(self):
        with pytest.raises(ValueError, match="at least one"):
            EnsembleStrategy([])

    def test_mismatched_weights_raises(self, prices_dict):
        s1 = BuyAndHold()
        with pytest.raises(ValueError):
            EnsembleStrategy([s1], strategy_weights=[0.5, 0.5])
