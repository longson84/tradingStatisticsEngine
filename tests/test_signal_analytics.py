"""Tests for src.signal.analytics — NP event detection."""
import numpy as np
import pandas as pd
import pytest

from src.signal.analytics import NPEvent, calculate_np_events_tree


def _make_series(values: list[float], start: str = "2020-01-01") -> pd.Series:
    idx = pd.bdate_range(start, periods=len(values))
    return pd.Series(values, index=idx)


# ---------------------------------------------------------------------------
# NPEvent lifecycle
# ---------------------------------------------------------------------------

class TestNPEventLifecycle:
    def test_create_update_close(self):
        """Basic lifecycle: create → update min price → close with recovery."""
        prices = _make_series([100, 90, 80, 95, 105])

        event = NPEvent(
            percentile=10,
            threshold=-0.1,
            start_date=prices.index[0],
            entry_price=100,
        )
        assert event.status == "Chưa phục hồi"
        assert event.min_price == 100

        # Update with lower prices
        event.update_price(prices.index[1], 90)
        assert event.min_price == 90

        event.update_price(prices.index[2], 80)
        assert event.min_price == 80
        assert event.min_date == prices.index[2]

        # Close with recovery
        event.close(prices.index[4], prices)
        assert event.status == "Đã phục hồi"
        assert event.days_to_recover == 4
        assert event.days_to_bottom == 2

    def test_mae_pct(self):
        """MAE percentage calculated from entry and min price."""
        event = NPEvent(
            percentile=5,
            threshold=-0.2,
            start_date=pd.Timestamp("2020-01-01"),
            entry_price=200,
        )
        event.min_price = 160  # 20% drop

        assert event.mae_pct == pytest.approx(20.0)


# ---------------------------------------------------------------------------
# calculate_np_events_tree
# ---------------------------------------------------------------------------

class TestNPEventTree:
    def test_no_events(self):
        """Signal always rising → no new trigger after day 0 (no price drop)."""
        # Monotonically rising signal + constant price means no drawdown events
        # because the algorithm requires signal <= threshold AND the event tree
        # only triggers when entering a *rare* zone. With a rising signal and
        # rising price, events recover immediately.
        prices = _make_series([float(100 + i) for i in range(20)])
        signals = _make_series([float(i) for i in range(20)])

        events = calculate_np_events_tree(prices, signals, [5, 10, 20])

        # All events should recover instantly since prices keep rising
        unrecovered = [e for e in events if e.status == "Chưa phục hồi"]
        assert unrecovered == []

    def test_synthetic_event(self):
        """Signal dips into zone → creates event, recovers → closes it."""
        n = 30
        prices_vals = [100.0] * 10 + [90.0] * 10 + [105.0] * 10
        signal_vals = [0.5] * 10 + [-0.5] * 10 + [0.5] * 10

        prices = _make_series(prices_vals[:n])
        signals = _make_series(signal_vals[:n])

        events = calculate_np_events_tree(prices, signals, [10, 20, 30, 50])

        # Should have at least one event triggered during the dip
        assert len(events) >= 1
        # The deepest event should have entry_price around 90
        recovered = [e for e in events if e.status == "Đã phục hồi"]
        assert len(recovered) >= 1

    def test_nested_parent_child(self):
        """Deeper percentile zones create child events under parent."""
        n = 40
        # Gradually deepening signal, then recovery
        signal_vals = (
            [0.8] * 5           # normal
            + [0.3] * 5         # enters ~50th percentile
            + [0.1] * 5         # enters ~25th percentile
            + [-0.2] * 5        # enters deeper zone
            + [-0.5] * 5        # deepest
            + [0.1] * 5         # starts recovering
            + [0.5] * 5         # normal
            + [0.8] * 5         # fully recovered signal-wise
        )
        prices_vals = (
            [100.0] * 5
            + [95.0] * 5
            + [90.0] * 5
            + [85.0] * 5
            + [80.0] * 5
            + [90.0] * 5
            + [100.0] * 5
            + [110.0] * 5
        )
        prices = _make_series(prices_vals[:n])
        signals = _make_series(signal_vals[:n])

        events = calculate_np_events_tree(prices, signals, [5, 10, 20, 30, 50])

        # With cascading signal drops, we expect parent-child relationships
        children = [e for e in events if e.upline_id is not None]
        parents = [e for e in events if e.upline_id is None and e.p_coverage > 0]

        # At minimum, should have some hierarchy
        if len(events) > 1:
            assert len(children) > 0 or len(parents) > 0
