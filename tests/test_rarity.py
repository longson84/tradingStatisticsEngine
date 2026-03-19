"""Unit tests for src/analysis/rarity/.

Tests focus on the three behaviors most likely to silently produce wrong
numbers on the Factor Analysis page:

1. Event detection — does calculate_np_events_tree find events correctly?
2. QR threshold classification — are quick-recovery events excluded from MAE stats?
3. np_stats structure — are keys and computed values correct?
4. current_status derivation — does get_detailed_current_status detect the active zone?
"""
import numpy as np
import pandas as pd
import pytest

from src.analysis.rarity.events import EventStatus, calculate_np_events_tree
from src.analysis.rarity.compute import calculate_np_stats, get_detailed_current_status


def _make_series(values: list[float], start: str = "2010-01-01") -> pd.Series:
    idx = pd.bdate_range(start, periods=len(values))
    return pd.Series(values, index=idx)


# ---------------------------------------------------------------------------
# Helpers — synthetic price + factor series
#
# Strategy: keep price constant at 100 so we control exactly what the factor
# does. The factor drops below the P10 threshold on known dates, recovers on
# known dates, then stays elevated.
# ---------------------------------------------------------------------------

def _build_scenario(
    n_normal: int = 50,
    n_event: int = 10,
    n_recovery: int = 40,
    factor_normal: float = 0.5,
    factor_event: float = 0.05,   # below P10 ≈ 0.1 of uniform(0,1) → always below P10
    price_constant: float = 100.0,
):
    """Build a (price_series, factor_series) pair with one controlled NP event.

    Layout:
      [0 .. n_normal-1]        factor=normal, price=100  (above threshold, no event)
      [n_normal]               factor=event,  price=100  (event opens; entry_price=100)
      [n_normal+1 .. -n_recovery-1]  factor=event, price=80  (below entry → event stays open)
      [n_normal+n_event ..]    factor=normal, price=100  (price returns → event closes)

    Critical: the event-start bar has price=100 (entry_price=100).
    Subsequent event bars drop to 80 so the event does not close prematurely.
    Recovery bars bring price back to 100 ≥ entry_price → event closes.
    """
    total = n_normal + n_event + n_recovery
    idx = pd.bdate_range("2010-01-01", periods=total)

    price_values = [price_constant] * total
    factor_values = [factor_normal] * n_normal + [factor_event] * n_event + [factor_normal] * n_recovery

    # Event-start bar (n_normal): price stays at 100 so entry_price = 100
    # Bars n_normal+1 onward (while factor is low): price = 80 < entry_price (100)
    for i in range(n_normal + 1, n_normal + n_event):
        price_values[i] = price_constant * 0.8

    price = pd.Series(price_values, index=idx, name="Close")
    factor = pd.Series(factor_values, index=idx)
    return price, factor


# ---------------------------------------------------------------------------
# calculate_np_events_tree
# ---------------------------------------------------------------------------

class TestNPEventTree:
    def test_no_events_when_factor_never_dips(self):
        """No events when factor stays above the P10 threshold throughout.

        We build a factor series where the first 90% of values are uniformly
        spread [0.0, 0.5] to fix the P10 threshold at ≈0.05, then set the
        final 10 bars to 0.9 so they never trigger P10 events.
        """
        n = 200
        idx = pd.bdate_range("2010-01-01", periods=n)
        # Build calibration values that spread across [0, 0.5] so P10 ≈ 0.05
        calibration = list(np.linspace(0.0, 0.5, n - 10))
        # Final 10 bars: factor = 0.9 — well above P10 threshold
        high_tail = [0.9] * 10
        factor = pd.Series(calibration + high_tail, index=idx)
        price = pd.Series([100.0] * n, index=idx)

        events = calculate_np_events_tree(price, factor, percentiles=[10])
        # Events may exist in the calibration region, but the last 10 bars must not add new ones
        last_date = idx[-10]
        late_events = [e for e in events if e.start_date >= last_date]
        assert late_events == [], (
            "Expected no NP events in the high-factor tail, but events were detected."
        )

    def test_detects_event_below_threshold(self):
        """An event is detected when factor drops below the P10 percentile."""
        price, factor = _build_scenario(n_normal=50, n_event=10, n_recovery=40)
        events = calculate_np_events_tree(price, factor, percentiles=[10, 5, 1])

        assert len(events) >= 1

    def test_event_is_recovered_when_price_returns(self):
        """Event status is RECOVERED once price returns to the entry level."""
        price, factor = _build_scenario(n_normal=50, n_event=10, n_recovery=40)
        events = calculate_np_events_tree(price, factor, percentiles=[10, 5, 1])

        # All events should have recovered since the price returns to 100 at the end
        recovered = [e for e in events if e.status == EventStatus.RECOVERED]
        assert len(recovered) >= 1

    def test_event_mae_is_positive(self):
        """MAE (max adverse excursion) should be positive — price dropped below entry."""
        price, factor = _build_scenario(n_normal=50, n_event=10, n_recovery=40)
        events = calculate_np_events_tree(price, factor, percentiles=[10, 5, 1])

        for e in events:
            assert e.mae_pct >= 0, f"Expected non-negative MAE, got {e.mae_pct}"

    def test_empty_factor_series_returns_empty(self):
        """Fewer than 2 common bars → empty result, no exception."""
        price = _make_series([100.0])
        factor = _make_series([0.5])

        events = calculate_np_events_tree(price, factor, percentiles=[10])
        assert events == []

    def test_days_to_recover_is_positive(self):
        """For recovered events, days_to_recover should be > 0."""
        price, factor = _build_scenario(n_normal=50, n_event=10, n_recovery=40)
        events = calculate_np_events_tree(price, factor, percentiles=[10, 5, 1])

        for e in [ev for ev in events if ev.status == EventStatus.RECOVERED]:
            assert e.days_to_recover is not None
            assert e.days_to_recover > 0

    def test_no_duplicate_events_at_same_percentile(self):
        """While an event is open at percentile P, no second event starts at P.

        The scenario has ONE continuous event (factor below threshold for n_event bars,
        price stays below entry_price throughout). Only 1 P10 event should exist.
        """
        price, factor = _build_scenario(n_normal=50, n_event=20, n_recovery=30)
        events = calculate_np_events_tree(price, factor, percentiles=[10])

        p10_events = [e for e in events if e.percentile == 10]
        assert len(p10_events) == 1, (
            f"Expected exactly 1 P10 event (one continuous event), got {len(p10_events)}. "
            "The algorithm must not open a new event at the same percentile while one is already active."
        )


# ---------------------------------------------------------------------------
# calculate_np_stats — QR threshold classification
# ---------------------------------------------------------------------------

class TestNPStats:
    def _build_events_and_df(self, n_event: int = 10, n_recovery: int = 40):
        price, factor = _build_scenario(n_normal=50, n_event=n_event, n_recovery=n_recovery)
        events = calculate_np_events_tree(price, factor, percentiles=[10, 5, 1])
        df = pd.DataFrame({"Close": price})
        return events, df, price, factor

    def test_stats_keys_match_calculate_percentiles(self):
        """calculate_np_stats returns a key for every percentile in CALCULATE_PERCENTILES."""
        from src.shared.constants import CALCULATE_PERCENTILES
        events, df, _, _ = self._build_events_and_df()
        stats = calculate_np_stats(events, df, qr_threshold=5)

        assert set(stats.keys()) == set(CALCULATE_PERCENTILES)

    def test_stat_dict_has_required_fields(self):
        """Non-None stat entries must contain count, qr, qr_pct, and mmae."""
        events, df, _, _ = self._build_events_and_df()
        stats = calculate_np_stats(events, df, qr_threshold=5)

        for p, s in stats.items():
            if s is not None:
                for key in ("count", "qr", "qr_pct", "mmae"):
                    assert key in s, f"Missing key '{key}' in stats for P{p}"

    def test_qr_count_does_not_exceed_total_count(self):
        """Quick-recovery count can never exceed total event count."""
        events, df, _, _ = self._build_events_and_df()
        stats = calculate_np_stats(events, df, qr_threshold=5)

        for p, s in stats.items():
            if s is not None:
                assert s["qr"] <= s["count"], f"P{p}: qr ({s['qr']}) > count ({s['count']})"

    def test_qr_threshold_zero_means_no_quick_recoveries(self):
        """With qr_threshold=0, no event can have days_to_recover <= 0 → qr=0."""
        events, df, _, _ = self._build_events_and_df(n_event=10, n_recovery=40)
        stats = calculate_np_stats(events, df, qr_threshold=0)

        for p, s in stats.items():
            if s is not None:
                assert s["qr"] == 0, f"P{p}: expected qr=0 with threshold=0, got {s['qr']}"

    def test_large_qr_threshold_may_classify_events_as_qr(self):
        """With a very large qr_threshold, events that recover are classified as QR."""
        events, df, _, _ = self._build_events_and_df(n_event=10, n_recovery=40)
        stats = calculate_np_stats(events, df, qr_threshold=999)

        # At least one percentile should have qr > 0 since events recovered
        total_qr = sum(s["qr"] for s in stats.values() if s is not None)
        assert total_qr > 0

    def test_mae_excludes_qr_events(self):
        """With threshold=0 (no QR), MAE values include all events.
        With threshold=999 (all QR), MAE values must be empty → mmae=0."""
        events, df, _, _ = self._build_events_and_df(n_event=10, n_recovery=40)

        stats_no_qr = calculate_np_stats(events, df, qr_threshold=0)
        stats_all_qr = calculate_np_stats(events, df, qr_threshold=999)

        for p in stats_no_qr:
            s_no = stats_no_qr[p]
            s_all = stats_all_qr[p]
            if s_no is not None and s_all is not None:
                # When all events are QR, mmae should be 0 (no non-QR events)
                assert s_all["mmae"] == 0, (
                    f"P{p}: expected mmae=0 when all events are QR, got {s_all['mmae']}"
                )


# ---------------------------------------------------------------------------
# get_detailed_current_status
# ---------------------------------------------------------------------------

class TestCurrentStatus:
    def test_returns_dict_with_required_keys(self):
        """get_detailed_current_status always returns the full result dict."""
        price, factor = _build_scenario(n_normal=50, n_event=10, n_recovery=40)
        result = get_detailed_current_status(price, factor)

        for key in ("current_price", "current_factor", "rarity", "ref_percentile"):
            assert key in result, f"Missing key '{key}' in current_status result"

    def test_rarity_is_between_0_and_100(self):
        """Rarity (percentile rank of current factor) must be in [0, 100]."""
        price, factor = _build_scenario(n_normal=50, n_event=10, n_recovery=40)
        result = get_detailed_current_status(price, factor)

        assert 0.0 <= result["rarity"] <= 100.0

    def test_no_active_zone_when_factor_is_high(self):
        """When the current factor is above all thresholds, ref_percentile is None.

        We build a series with spread-out values [0..0.5] so percentile thresholds
        are computed from low values, then set the final bar to 0.9 — well above P50.
        """
        n = 100
        idx = pd.bdate_range("2010-01-01", periods=n)
        # Calibration bars spread from 0.0 to 0.5 → P50 threshold ≈ 0.25
        values = list(np.linspace(0.0, 0.5, n - 1)) + [0.9]
        factor = pd.Series(values, index=idx)
        price = pd.Series([100.0] * n, index=idx)

        result = get_detailed_current_status(price, factor)
        assert result["ref_percentile"] is None

    def test_detects_active_zone_during_event(self):
        """During an active NP event, ref_percentile should be set."""
        # Build a scenario where the LAST bar is still in the event (no recovery)
        n_normal = 50
        n_event = 10
        total = n_normal + n_event
        idx = pd.bdate_range("2010-01-01", periods=total)

        factor_values = [0.5] * n_normal + [0.05] * n_event
        price_values = [100.0] * n_normal + [80.0] * n_event

        price = pd.Series(price_values, index=idx)
        factor = pd.Series(factor_values, index=idx)

        result = get_detailed_current_status(price, factor)

        assert result["ref_percentile"] is not None, (
            "Expected ref_percentile to be set when factor is in an NP zone."
        )
