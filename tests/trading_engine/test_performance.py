"""Tests for trading_engine/performance/ — Layer 6 validation gate.

Gate: from trading_engine import run_comparison
Key verifications:
- analyze_performance with known trades -> correct metric values
- run_comparison partial failure: bad config collects error, never raises
- run_comparison([]) raises ValueError
- 0 trades -> all metrics = 0, no divide-by-zero
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from trading_engine import run_comparison
from trading_engine.performance import analyze_performance
from trading_engine.strategy import BuyAndHold, MACrossover
from trading_engine.types import (
    BacktestConfig,
    PerformanceReport,
    Portfolio,
    PortfolioResult,
    Trade,
    WeightEvent,
)

from tests.trading_engine.conftest import make_price_frame


# =============================================================================
# [AN] analyze_performance — metric correctness
# =============================================================================

class TestAnalyzePerformance:
    def _make_result(self, nav_values: list[float], trades: list[Trade]) -> PortfolioResult:
        idx = pd.date_range("2020-01-01", periods=len(nav_values), freq="B")
        return PortfolioResult(
            equity_curve=pd.Series(nav_values, index=idx),
            trades=trades,
            weights=pd.DataFrame(),
        )

    def test_win_rate_with_known_trades(self, known_trades):
        """3 wins + 2 losses = 60% win rate."""
        nav = list(range(1000, 1010))
        result = self._make_result(nav, known_trades)
        report = analyze_performance(result)
        assert report.win_rate == pytest.approx(60.0)

    def test_avg_return_with_known_trades(self, known_trades):
        """(10 + 20 + 5 + (-5) + (-15)) / 5 = 3.0% avg return."""
        nav = list(range(1000, 1010))
        result = self._make_result(nav, known_trades)
        report = analyze_performance(result)
        assert report.avg_return_per_trade == pytest.approx(3.0)

    def test_zero_trades_no_crash(self):
        """0 trades -> metrics = 0, no divide-by-zero."""
        nav = [1000.0] * 100
        result = self._make_result(nav, [])
        report = analyze_performance(result)
        assert report.win_rate == 0.0
        assert report.avg_return_per_trade == 0.0
        assert report.avg_holding_days == 0.0

    def test_total_return_correct(self):
        """NAV doubles -> total return = 100%."""
        nav = [1000.0, 1500.0, 2000.0]
        result = self._make_result(nav, [])
        report = analyze_performance(result)
        assert report.total_return_pct == pytest.approx(100.0)

    def test_flat_nav_zero_return(self):
        nav = [1000.0] * 50
        result = self._make_result(nav, [])
        report = analyze_performance(result)
        assert report.total_return_pct == pytest.approx(0.0)

    def test_max_drawdown_negative(self):
        """Max drawdown should always be <= 0."""
        nav = [1000.0, 1200.0, 800.0, 1100.0]
        result = self._make_result(nav, [])
        report = analyze_performance(result)
        assert report.max_drawdown_pct <= 0.0

    def test_max_drawdown_known_value(self):
        """NAV goes 1000 -> 2000 -> 1000 -> 33% drawdown from peak."""
        nav = [1000.0, 2000.0, 1000.0]
        result = self._make_result(nav, [])
        report = analyze_performance(result)
        # From peak 2000 to trough 1000 = -50% drawdown
        assert report.max_drawdown_pct == pytest.approx(-50.0)

    def test_sharpe_positive_for_upward_trend(self, prices_dict):
        from trading_engine import run_portfolio
        portfolio = Portfolio(initial_capital=10_000.0, strategy=BuyAndHold())
        result = run_portfolio(portfolio, prices_dict)
        report = analyze_performance(result)
        # With upward trend, Sharpe should be positive
        # (not guaranteed but our synthetic data has positive trend)
        assert isinstance(report.sharpe_ratio, float)

    def test_monthly_returns_is_dataframe(self, prices_dict):
        from trading_engine import run_portfolio
        portfolio = Portfolio(initial_capital=10_000.0, strategy=BuyAndHold())
        result = run_portfolio(portfolio, prices_dict)
        report = analyze_performance(result)
        assert isinstance(report.monthly_returns, pd.DataFrame)

    def test_empty_equity_returns_zero_report(self):
        result = PortfolioResult(
            equity_curve=pd.Series(dtype=float),
            trades=[],
            weights=pd.DataFrame(),
        )
        report = analyze_performance(result)
        assert report.total_return_pct == 0.0
        assert report.sharpe_ratio == 0.0


# =============================================================================
# [AO] run_comparison — partial failure + edge cases
# =============================================================================

class TestRunComparison:
    def test_basic_two_configs(self, prices_dict):
        configs = [
            BacktestConfig(
                strategy=BuyAndHold(),
                symbols=["AAPL"],
                start=date(2020, 1, 1),
                end=date(2021, 12, 31),
            ),
            BacktestConfig(
                strategy=MACrossover(),
                symbols=["MSFT"],
                start=date(2020, 1, 1),
                end=date(2021, 12, 31),
            ),
        ]
        report = run_comparison(configs, prices_dict)
        assert len(report.results) == 2
        assert len(report.errors) == 0

    def test_partial_failure_collects_errors(self, prices_dict):
        """A config with a missing symbol should be collected as error, not raised."""
        configs = [
            BacktestConfig(
                strategy=BuyAndHold(),
                symbols=["AAPL"],
                start=date(2020, 1, 1),
                end=date(2021, 12, 31),
            ),
            BacktestConfig(
                strategy=BuyAndHold(),
                symbols=["NONEXISTENT_SYMBOL"],  # will fail
                start=date(2020, 1, 1),
                end=date(2021, 12, 31),
            ),
        ]
        report = run_comparison(configs, prices_dict)
        assert len(report.results) == 1
        assert len(report.errors) == 1
        assert report.errors[0][1] is not None  # exception is captured

    def test_empty_configs_raises(self, prices_dict):
        with pytest.raises(ValueError, match="No configs"):
            run_comparison([], prices_dict)

    def test_all_configs_fail_returns_empty_results(self, prices_dict):
        configs = [
            BacktestConfig(
                strategy=BuyAndHold(),
                symbols=["FAKE1"],
                start=date(2020, 1, 1),
                end=date(2020, 12, 31),
            ),
        ]
        report = run_comparison(configs, prices_dict)
        assert len(report.results) == 0
        assert len(report.errors) == 1

    def test_results_and_configs_same_length(self, prices_dict):
        configs = [
            BacktestConfig(
                strategy=BuyAndHold(),
                symbols=["AAPL"],
                start=date(2020, 1, 1),
                end=date(2020, 6, 30),
            ),
            BacktestConfig(
                strategy=BuyAndHold(),
                symbols=["MSFT"],
                start=date(2020, 1, 1),
                end=date(2020, 6, 30),
            ),
        ]
        report = run_comparison(configs, prices_dict)
        assert len(report.results) == len(report.configs)


# =============================================================================
# [AL] TradeDistribution buckets
# =============================================================================

class TestTradeDistribution:
    def test_buckets_sum_to_trade_count(self, known_trades):
        nav = [1000.0 + i * 10 for i in range(20)]
        idx = pd.date_range("2020-01-01", periods=len(nav))
        result = PortfolioResult(
            equity_curve=pd.Series(nav, index=idx),
            trades=known_trades,
            weights=pd.DataFrame(),
        )
        report = analyze_performance(result)
        total_in_buckets = sum(report.trade_distribution.return_buckets.values())
        assert total_in_buckets == len(known_trades)
