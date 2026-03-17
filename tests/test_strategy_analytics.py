"""Tests for src.strategy.analytics — pure trade computation."""
import numpy as np
import pandas as pd
import pytest

from src.strategy.analytics import (
    Trade,
    build_equity_curve,
    build_trades,
    calculate_drawdown_during_trades,
    calculate_equity_curve_max_drawdown,
    calculate_max_drawdown,
    calculate_trade_performance,
)


def _make_price(values: list[float], start: str = "2020-01-01") -> pd.Series:
    idx = pd.bdate_range(start, periods=len(values))
    return pd.Series(values, index=idx, name="Close")


def _make_signals(index: pd.DatetimeIndex, true_positions: list[int]) -> pd.Series:
    s = pd.Series(False, index=index)
    for i in true_positions:
        s.iloc[i] = True
    return s


# ---------------------------------------------------------------------------
# build_trades
# ---------------------------------------------------------------------------

class TestBuildTrades:
    def test_basic(self):
        """Buy on day 1, sell on day 3 → one closed trade."""
        price = _make_price([100, 110, 120, 115])
        buy = _make_signals(price.index, [1])
        sell = _make_signals(price.index, [3])

        trades = build_trades(price, buy, sell)

        assert len(trades) == 1
        t = trades[0]
        assert t.status == "closed"
        assert t.entry_price == 110
        assert t.exit_price == 115
        assert t.return_pct == pytest.approx((115 / 110 - 1) * 100)

    def test_no_signals(self):
        """No buy/sell signals → no trades."""
        price = _make_price([100, 110, 120])
        buy = _make_signals(price.index, [])
        sell = _make_signals(price.index, [])

        assert build_trades(price, buy, sell) == []

    def test_open_trade(self):
        """Buy without sell → trade stays open."""
        price = _make_price([100, 110, 130])
        buy = _make_signals(price.index, [1])
        sell = _make_signals(price.index, [])

        trades = build_trades(price, buy, sell)

        assert len(trades) == 1
        assert trades[0].status == "open"
        assert trades[0].entry_price == 110
        # Open trade gets last price as exit_price for P&L tracking
        assert trades[0].exit_price == 130


# ---------------------------------------------------------------------------
# calculate_trade_performance
# ---------------------------------------------------------------------------

class TestPerformance:
    def test_empty(self):
        """Zero trades → zeroed performance."""
        perf = calculate_trade_performance([])

        assert perf.closed_trades == 0
        assert perf.win_rate == 0.0
        assert perf.total_return == 0.0
        assert perf.max_consecutive_losses == 0

    def test_with_trades(self):
        """Known trades → correct win_rate, total_return, max_consecutive_losses."""
        trades = [
            Trade(pd.Timestamp("2020-01-02"), 100, pd.Timestamp("2020-01-06"), 120, 20.0, 4, "closed"),
            Trade(pd.Timestamp("2020-01-07"), 120, pd.Timestamp("2020-01-10"), 108, -10.0, 3, "closed"),
            Trade(pd.Timestamp("2020-01-13"), 110, pd.Timestamp("2020-01-15"), 99, -10.0, 2, "closed"),
        ]
        perf = calculate_trade_performance(trades)

        assert perf.closed_trades == 3
        assert perf.win_count == 1
        assert perf.loss_count == 2
        assert perf.win_rate == pytest.approx(1 / 3 * 100)
        assert perf.max_consecutive_losses == 2

        # Compound return: (1.20) * (0.90) * (0.90) - 1 = -0.028 → -2.8%
        expected = (1.20 * 0.90 * 0.90 - 1) * 100
        assert perf.total_return == pytest.approx(expected)


# ---------------------------------------------------------------------------
# calculate_max_drawdown
# ---------------------------------------------------------------------------

class TestMaxDrawdown:
    def test_known_series(self):
        """Peak 200 → trough 100 → drawdown = -50%."""
        price = _make_price([100, 200, 150, 100, 120])
        dd = calculate_max_drawdown(price)

        assert dd == pytest.approx(-50.0)

    def test_monotonic_up(self):
        """Monotonically increasing → drawdown is 0%."""
        price = _make_price([100, 110, 120, 130])
        dd = calculate_max_drawdown(price)

        assert dd == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# build_equity_curve
# ---------------------------------------------------------------------------

class TestEquityCurve:
    def test_flat_when_out_of_trade(self):
        """Equity stays flat (cash) when not in a trade."""
        price = _make_price([100, 110, 120, 130, 140])
        buy = _make_signals(price.index, [])
        sell = _make_signals(price.index, [])

        equity = build_equity_curve(price, buy, sell, initial=1000.0)

        # All values should be 1000 — no trades, no change
        assert (equity == 1000.0).all()

    def test_tracks_price_in_trade(self):
        """Equity tracks price proportionally while in a trade."""
        price = _make_price([100, 100, 150, 200, 200])
        buy = _make_signals(price.index, [1])   # buy at 100
        sell = _make_signals(price.index, [3])   # sell at 200

        equity = build_equity_curve(price, buy, sell, initial=1000.0)

        # Day 0: out of trade → 1000
        assert equity.iloc[0] == pytest.approx(1000.0)
        # Day 1: enter at 100 → 1000
        assert equity.iloc[1] == pytest.approx(1000.0)
        # Day 2: price 150/100 → 1500
        assert equity.iloc[2] == pytest.approx(1500.0)
        # Day 3: sell at 200 → equity locks at 2000
        assert equity.iloc[3] == pytest.approx(2000.0)
        # Day 4: out of trade → stays 2000
        assert equity.iloc[4] == pytest.approx(2000.0)


# ---------------------------------------------------------------------------
# MAE / MFE
# ---------------------------------------------------------------------------

class TestMAEMFE:
    def test_mae_mfe_computed(self):
        """MAE/MFE are filled correctly per trade."""
        price = _make_price([100, 100, 80, 130, 110])
        trade = Trade(
            entry_date=price.index[1],
            entry_price=100,
            exit_date=price.index[4],
            exit_price=110,
            return_pct=10.0,
            holding_days=3,
            status="closed",
        )
        trades = calculate_drawdown_during_trades([trade], price)
        t = trades[0]

        # MAE: lowest = 80, (100-80)/100 = 20%
        assert t.mae_pct == pytest.approx(20.0)
        assert t.mae_price == pytest.approx(80.0)

        # MFE: highest = 130, (130-100)/100 = 30%
        assert t.mfe_pct == pytest.approx(30.0)
        assert t.mfe_price == pytest.approx(130.0)
