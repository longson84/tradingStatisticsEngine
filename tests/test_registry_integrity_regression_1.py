"""Registry integrity tests.

Regression: ISSUE-002 — Parameter Sweep crashes with KeyError on strategy type
Found by /qa on 2026-03-18
Report: .gstack/qa-reports/qa-report-localhost-2026-03-18.md
"""
from src.strategy.registry import STRATEGY_NAMES
from src.app.strategy_sidebar_factories import SIDEBAR_REGISTRY, SWEEP_SIDEBAR_REGISTRY


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
