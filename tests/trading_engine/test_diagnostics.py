"""Tests for trading_engine/diagnostics/ — Diagnostics validation gate.

Gate: from trading_engine.diagnostics import assert_no_leakage
Key verifications:
- Clean strategies pass the leakage check
- A strategy that uses future data fails with StrategyOutputError
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from trading_engine.diagnostics import assert_no_leakage
from trading_engine.strategy import BuyAndHold, MACrossover
from trading_engine.strategy.base import BaseStrategy
from trading_engine.types import PriceFrame, StrategyOutputError

from tests.trading_engine.conftest import make_price_frame


# =============================================================================
# [AR] Clean strategies pass
# =============================================================================

class TestNoLeakagePassesClearStrategies:
    def test_buy_and_hold_passes(self):
        prices = {"X": make_price_frame("X")}
        assert_no_leakage(BuyAndHold(), ["X"], prices)

    def test_ma_crossover_passes(self):
        prices = {"X": make_price_frame("X")}
        assert_no_leakage(MACrossover(fast_length=5, slow_length=20), ["X"], prices)

    def test_multi_symbol_passes(self):
        prices = {
            "A": make_price_frame("A", seed=10),
            "B": make_price_frame("B", seed=11),
        }
        assert_no_leakage(BuyAndHold(), ["A", "B"], prices)


# =============================================================================
# [AS] Leaky strategy is detected
# =============================================================================

class _LeakyStrategy(BaseStrategy):
    """Strategy that looks ahead by using shifted(-1) close prices.
    This simulates a common look-ahead bias bug: using tomorrow's price today.
    """
    def _compute_weights(self, symbols, prices, regime=None) -> pd.DataFrame:
        result = {}
        for symbol in symbols:
            if symbol not in prices:
                continue
            close = prices[symbol].data["close"]
            # BUG: shift(-1) means we're using tomorrow's price today
            future_return = close.shift(-1) / close - 1
            # Buy when tomorrow's return is positive (look-ahead bias!)
            signal = (future_return > 0).astype(float).fillna(0.0)
            result[symbol] = signal
        return pd.DataFrame(result)


class TestLeakageDetection:
    def test_leaky_strategy_raises(self):
        prices = {"X": make_price_frame("X")}
        with pytest.raises(StrategyOutputError, match="Look-ahead bias"):
            assert_no_leakage(_LeakyStrategy(), ["X"], prices, truncate_bars=30)

    def test_error_message_includes_details(self):
        prices = {"X": make_price_frame("X")}
        with pytest.raises(StrategyOutputError) as exc_info:
            assert_no_leakage(_LeakyStrategy(), ["X"], prices)
        assert "Look-ahead bias" in str(exc_info.value)

    def test_insufficient_data_skips_gracefully(self):
        """If prices are too small to truncate, should not raise."""
        prices = {"X": make_price_frame("X", days=10)}
        # truncate_bars=20 > days=10, should skip gracefully
        assert_no_leakage(BuyAndHold(), ["X"], prices, truncate_bars=20)


# =============================================================================
# Final gate: zero streamlit imports in trading_engine/
# =============================================================================

class TestZeroStreamlitImports:
    def test_no_streamlit_in_trading_engine(self):
        """trading_engine package must not import streamlit anywhere."""
        import importlib
        import pkgutil
        import trading_engine

        # Walk all modules in trading_engine
        package = trading_engine
        package_path = package.__path__

        for importer, modname, ispkg in pkgutil.walk_packages(
            path=package_path, prefix=package.__name__ + ".", onerror=lambda x: None
        ):
            try:
                mod = importlib.import_module(modname)
                # Check that streamlit is not imported in any module
                assert "streamlit" not in (getattr(mod, "__module__", "") or ""), (
                    f"{modname} references streamlit"
                )
            except ImportError:
                pass

        # Also check source files directly
        import os
        from pathlib import Path
        te_root = Path(trading_engine.__file__).parent
        for py_file in te_root.rglob("*.py"):
            content = py_file.read_text()
            assert "import streamlit" not in content, (
                f"Found 'import streamlit' in {py_file}"
            )
            assert "from streamlit" not in content, (
                f"Found 'from streamlit' in {py_file}"
            )
