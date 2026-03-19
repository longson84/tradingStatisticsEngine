"""Registry integrity tests.

Regression: ISSUE-002 — Parameter Sweep crashes with KeyError on strategy type
Found by /qa on 2026-03-18
Report: .gstack/qa-reports/qa-report-localhost-2026-03-18.md
"""
import pytest

from src.strategy.registry import STRATEGY_NAMES
from src.strategy.base import BaseStrategy
from src.app.strategy_sidebar_factories import (
    SIDEBAR_REGISTRY,
    SWEEP_SIDEBAR_REGISTRY,
    build_from_sweep_config,
    sweep_label,
    should_skip_sweep_length,
)

# ---------------------------------------------------------------------------
# Minimal sweep configs — one per strategy type.
# Each config must supply every key that build_from_sweep_config /
# sweep_label / should_skip_sweep_length reads for that strategy type.
# ---------------------------------------------------------------------------
_SWEEP_CONFIGS = {
    "Price vs MA": {
        "ma_type": "SMA",
        "buy_lag": 0,
        "sell_lag": 2,
    },
    "MA Crossover": {
        "sweep_dimension": "fast",
        "fast_ma_type": "EMA",
        "slow_ma_type": "SMA",
        "fixed_length": 200,
        "buy_lag": 1,
        "sell_lag": 1,
    },
    "Bollinger Bands": {
        "sweep_dimension": "period",
        "fixed_value": 2.0,
    },
    "Donchian Breakout": {
        "sweep_dimension": "entry",
        "fixed_length": 10,
    },
}
_SWEEP_LENGTH = 20  # representative length for all strategies


class TestRegistryIntegrity:
    def test_strategy_names_covered_by_sidebar_registry(self):
        """Every strategy name must have a corresponding entry in SIDEBAR_REGISTRY.

        Prevents: page crash when strategy dropdown (from STRATEGY_NAMES) returns
        a name that doesn't exist as a SIDEBAR_REGISTRY key.
        """
        missing = [n for n in STRATEGY_NAMES if n not in SIDEBAR_REGISTRY]
        assert missing == [], (
            f"Strategy names missing from SIDEBAR_REGISTRY: {missing}. "
            "Update SIDEBAR_REGISTRY keys to match DISPLAY_NAME values."
        )

    def test_strategy_names_covered_by_sweep_sidebar_registry(self):
        """Every strategy name must have a corresponding entry in SWEEP_SIDEBAR_REGISTRY.

        Prevents: Parameter Sweep crash when sweep dropdown (from STRATEGY_NAMES) returns
        a name that doesn't exist as a SWEEP_SIDEBAR_REGISTRY key.
        """
        missing = [n for n in STRATEGY_NAMES if n not in SWEEP_SIDEBAR_REGISTRY]
        assert missing == [], (
            f"Strategy names missing from SWEEP_SIDEBAR_REGISTRY: {missing}. "
            "Update SWEEP_SIDEBAR_REGISTRY keys to match DISPLAY_NAME values."
        )

    def test_all_registries_have_same_keys(self):
        """All three registries must cover the same set of strategy names."""
        sidebar_keys = set(SIDEBAR_REGISTRY.keys())
        sweep_keys = set(SWEEP_SIDEBAR_REGISTRY.keys())
        names = set(STRATEGY_NAMES)
        assert sidebar_keys == names, f"SIDEBAR_REGISTRY keys {sidebar_keys} != STRATEGY_NAMES {names}"
        assert sweep_keys == names, f"SWEEP_SIDEBAR_REGISTRY keys {sweep_keys} != STRATEGY_NAMES {names}"

    def test_sweep_configs_cover_all_strategy_names(self):
        """_SWEEP_CONFIGS must cover every strategy name in STRATEGY_NAMES.

        Prevents this test class from silently skipping a newly added strategy.
        """
        missing = [n for n in STRATEGY_NAMES if n not in _SWEEP_CONFIGS]
        assert missing == [], (
            f"_SWEEP_CONFIGS is missing entries for: {missing}. "
            "Add a minimal config dict so the dispatch function tests below cover it."
        )


class TestSweepDispatchFunctions:
    """Ensure build_from_sweep_config / sweep_label / should_skip_sweep_length
    handle every registered strategy without raising ValueError or KeyError.

    Prevents: Parameter Sweep crash when a new strategy is added to STRATEGY_REGISTRY
    but the dispatch if/elif chains in strategy_sidebar_factories.py are not updated.
    """

    @pytest.mark.parametrize("strategy_type", STRATEGY_NAMES)
    def test_build_from_sweep_config_does_not_raise(self, strategy_type):
        """build_from_sweep_config must return a BaseStrategy for every registered name."""
        config = _SWEEP_CONFIGS[strategy_type]
        result = build_from_sweep_config(strategy_type, config, _SWEEP_LENGTH)
        assert isinstance(result, BaseStrategy), (
            f"build_from_sweep_config('{strategy_type}', ...) returned {type(result)}, "
            "expected a BaseStrategy subclass."
        )

    @pytest.mark.parametrize("strategy_type", STRATEGY_NAMES)
    def test_sweep_label_does_not_raise(self, strategy_type):
        """sweep_label must return a non-empty string for every registered name."""
        config = _SWEEP_CONFIGS[strategy_type]
        label = sweep_label(strategy_type, config, _SWEEP_LENGTH)
        assert isinstance(label, str) and label, (
            f"sweep_label('{strategy_type}', ...) returned an empty or non-string value."
        )

    @pytest.mark.parametrize("strategy_type", STRATEGY_NAMES)
    def test_should_skip_sweep_length_does_not_raise(self, strategy_type):
        """should_skip_sweep_length must return a bool for every registered name."""
        config = _SWEEP_CONFIGS[strategy_type]
        result = should_skip_sweep_length(strategy_type, config, _SWEEP_LENGTH)
        assert isinstance(result, bool), (
            f"should_skip_sweep_length('{strategy_type}', ...) returned {type(result)}, expected bool."
        )
