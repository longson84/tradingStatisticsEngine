"""Tests for trading_engine/portfolio/ — Layer 5 validation gate.

Gate: from trading_engine import run_portfolio
Key verifications:
- Correct NAV on known price series
- max_leverage enforcement
- Regime config wiring
- Long and short P&L math
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from trading_engine import run_portfolio
from trading_engine.strategy.base import BaseStrategy
from trading_engine.types import (
    Portfolio,
    PriceFrame,
    RegimeSeries,
)

from tests.trading_engine.conftest import make_price_frame


# =============================================================================
# Helpers
# =============================================================================

class _ConstantWeightStrategy(BaseStrategy):
    """Applies constant weight to all symbols — for predictable NAV math."""
    def __init__(self, weight: float = 1.0):
        self.weight = weight

    def _compute_weights(self, symbols, prices, regime=None) -> pd.DataFrame:
        idx = prices[symbols[0]].data.index
        return pd.DataFrame({s: self.weight for s in symbols}, index=idx)


class _SpecificWeightStrategy(BaseStrategy):
    """Applies a pre-defined weight Series — for deterministic trade tests."""
    def __init__(self, weights_map: dict[str, list[float]]):
        self.weights_map = weights_map

    def _compute_weights(self, symbols, prices, regime=None) -> pd.DataFrame:
        idx = prices[symbols[0]].data.index
        data = {}
        for s in symbols:
            if s in self.weights_map:
                vals = self.weights_map[s]
                data[s] = pd.Series(vals[:len(idx)], index=idx[:len(vals)])
        return pd.DataFrame(data).reindex(idx).fillna(0.0)


# =============================================================================
# [AC] NAV correctness on known price series
# =============================================================================

class TestRunPortfolioNAV:
    def _flat_prices(self, symbol: str, n: int, start_price: float, daily_return: float) -> dict[str, PriceFrame]:
        """Prices with exact constant daily return."""
        prices = start_price * (1 + daily_return) ** np.arange(n)
        df = pd.DataFrame(
            {"open": prices, "high": prices, "low": prices, "close": prices},
            index=pd.date_range("2020-01-01", periods=n, freq="B"),
        )
        return {symbol: PriceFrame(symbol=symbol, data=df, source="test")}

    def test_fully_invested_grows_with_price(self):
        """100% long in asset with +1% daily return -> NAV grows ~1% daily."""
        prices = self._flat_prices("X", n=20, start_price=100.0, daily_return=0.01)
        portfolio = Portfolio(
            initial_capital=1000.0,
            strategy=_ConstantWeightStrategy(weight=1.0),
        )
        result = run_portfolio(portfolio, prices)
        assert result.equity_curve.iloc[-1] > result.equity_curve.iloc[0]
        # After 19 trading days at 1% daily, NAV should be close to 1000 * 1.01^19
        expected = 1000.0 * (1.01 ** 19)
        assert result.equity_curve.iloc[-1] == pytest.approx(expected, rel=0.01)

    def test_flat_position_nav_stays_constant(self):
        """0% weight -> NAV should stay at initial capital."""
        prices = self._flat_prices("X", n=20, start_price=100.0, daily_return=0.05)
        portfolio = Portfolio(
            initial_capital=1000.0,
            strategy=_ConstantWeightStrategy(weight=0.0),
        )
        result = run_portfolio(portfolio, prices)
        # After the first bar (lag), NAV should be flat
        nav_changes = result.equity_curve.diff().dropna()
        assert nav_changes.abs().sum() == pytest.approx(0.0, abs=1e-6)

    def test_equity_curve_length_matches_prices(self, prices_dict):
        from trading_engine.strategy import BuyAndHold
        portfolio = Portfolio(initial_capital=10_000.0, strategy=BuyAndHold())
        result = run_portfolio(portfolio, prices_dict)
        price_len = len(prices_dict["AAPL"].data)
        assert len(result.equity_curve) == price_len

    def test_initial_capital_is_nav_at_start(self, prices_dict):
        from trading_engine.strategy import BuyAndHold
        portfolio = Portfolio(initial_capital=5_000.0, strategy=BuyAndHold())
        result = run_portfolio(portfolio, prices_dict)
        assert result.equity_curve.iloc[0] == pytest.approx(5_000.0)


# =============================================================================
# [AG] max_leverage enforcement
# =============================================================================

class TestMaxLeverage:
    def test_sum_abs_weights_never_exceeds_limit(self, prices_dict):
        from trading_engine.strategy import BuyAndHold
        portfolio = Portfolio(
            initial_capital=10_000.0,
            strategy=BuyAndHold(weight=1.0),
            max_leverage=1.0,
        )
        result = run_portfolio(portfolio, prices_dict)
        abs_sum = result.weights.abs().sum(axis=1)
        # max leverage = 1.0, 3 symbols each at 1.0 -> should be capped
        assert (abs_sum <= 1.0 + 1e-9).all(), f"Max was {abs_sum.max()}"

    def test_leverage_2_allows_double(self, prices_dict):
        from trading_engine.strategy import BuyAndHold
        portfolio = Portfolio(
            initial_capital=10_000.0,
            strategy=BuyAndHold(weight=1.0),
            max_leverage=2.0,
        )
        result = run_portfolio(portfolio, prices_dict)
        abs_sum = result.weights.abs().sum(axis=1)
        assert (abs_sum <= 2.0 + 1e-9).all()

    def test_single_symbol_unaffected_by_leverage(self):
        """Single symbol at weight=0.8 with leverage=1.0 should not be scaled."""
        prices = {"X": make_price_frame("X")}
        portfolio = Portfolio(
            initial_capital=1000.0,
            strategy=_ConstantWeightStrategy(weight=0.8),
            max_leverage=1.0,
        )
        result = run_portfolio(portfolio, prices)
        # 0.8 < 1.0, so no scaling needed
        assert result.weights["X"].max() == pytest.approx(0.8)


# =============================================================================
# [AJ] PortfolioResult structure
# =============================================================================

class TestPortfolioResult:
    def test_result_has_all_fields(self, prices_dict, simple_strategy):
        portfolio = Portfolio(initial_capital=10_000.0, strategy=simple_strategy)
        result = run_portfolio(portfolio, prices_dict)
        assert result.equity_curve is not None
        assert result.trades is not None
        assert result.weights is not None

    def test_weights_match_strategy_output(self, prices_dict):
        from trading_engine.strategy import BuyAndHold
        strategy = BuyAndHold(weight=0.5)
        portfolio = Portfolio(initial_capital=1000.0, strategy=strategy, max_leverage=2.0)
        result = run_portfolio(portfolio, prices_dict)
        # 0.5 per symbol, 3 symbols, max_leverage=2.0 -> no capping needed (sum=1.5)
        assert result.weights.max().max() == pytest.approx(0.5)

    def test_trades_are_trade_instances(self, prices_dict, simple_strategy):
        portfolio = Portfolio(initial_capital=10_000.0, strategy=simple_strategy)
        result = run_portfolio(portfolio, prices_dict)
        from trading_engine.types import Trade
        for trade in result.trades:
            assert isinstance(trade, Trade)
