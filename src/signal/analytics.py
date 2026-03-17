import numpy as np
import pandas as pd
import uuid
from enum import Enum
from typing import List, Optional

from src.constants import CALCULATE_PERCENTILES, MIN_RECOVERY_DAYS_THRESHOLD


class EventStatus(str, Enum):
    UNRECOVERED = "Chưa phục hồi"
    RECOVERED = "Đã phục hồi"


class NPEvent:
    def __init__(self, percentile: float, threshold: float, start_date, entry_price: float, upline_id: Optional[str] = None):
        self.id = str(uuid.uuid4())
        self.percentile = percentile
        self.threshold = threshold
        self.start_date = start_date
        self.entry_price = entry_price
        self.upline_id = upline_id

        self.min_price = entry_price
        self.min_date = start_date

        self.status = EventStatus.UNRECOVERED
        self.recovery_date = None
        self.days_to_recover = None
        self.days_to_bottom = 0

        self.children_ids = []
        self.p_coverage = 0

    def update_price(self, date, price):
        if price < self.min_price:
            self.min_price = price
            self.min_date = date

    def close(self, recovery_date, price_series):
        self.status = EventStatus.RECOVERED
        self.recovery_date = recovery_date
        try:
            start_idx = price_series.index.get_loc(self.start_date)
            rec_idx = price_series.index.get_loc(recovery_date)
            self.days_to_recover = rec_idx - start_idx
            min_idx = price_series.index.get_loc(self.min_date)
            self.days_to_bottom = min_idx - start_idx
        except Exception:
            start_i = price_series.index.searchsorted(self.start_date)
            rec_i = price_series.index.searchsorted(recovery_date)
            min_i = price_series.index.searchsorted(self.min_date)
            self.days_to_recover = int(rec_i - start_i)
            self.days_to_bottom = int(min_i - start_i)

    @property
    def mae_pct(self):
        """Max adverse excursion — how far price fell from entry (positive %)."""
        return (1 - self.min_price / self.entry_price) * 100


def calculate_signal_percentiles(signal_series: pd.Series, percentiles=CALCULATE_PERCENTILES) -> pd.DataFrame:
    """Return a DataFrame of signal threshold values at each percentile."""
    clean = signal_series.dropna()
    return pd.DataFrame([
        {"Percentile": p, "Threshold": np.percentile(clean, p)}
        for p in percentiles
    ])


def calculate_np_events_tree(
    price_series: pd.Series,
    signal_series: pd.Series,
    percentiles: list,
) -> List[NPEvent]:
    """
    Detect NP events using a tree structure.

    Trigger: signal <= percentile_threshold AND price < prev_price
    Recovery: price returns to >= entry_price
    Parent: the closest active event (by entry_price) that contains this one.
    """
    common_idx = price_series.index.intersection(signal_series.index)
    if len(common_idx) < 2:
        return []

    prices = price_series.loc[common_idx]
    signals = signal_series.loc[common_idx]

    clean_signals = signal_series.dropna()
    threshold_map = {p: np.percentile(clean_signals, p) for p in percentiles}
    sorted_percentiles = sorted(percentiles)

    active_events: List[NPEvent] = []
    closed_events: List[NPEvent] = []

    for i in range(1, len(common_idx)):
        current_date = common_idx[i]
        current_price = prices.iloc[i]
        current_signal = signals.iloc[i]

        # A. Check recovery for all active events
        still_active = []
        for event in active_events:
            event.update_price(current_date, current_price)
            if current_price >= event.entry_price:
                event.close(current_date, prices)
                closed_events.append(event)
            else:
                still_active.append(event)
        active_events = still_active

        # B. Check new trigger: signal entering a rare zone
        # Only trigger the tightest applicable percentile (smallest p)
        target_p = None
        target_threshold = None
        for p in sorted_percentiles:
            if current_signal <= threshold_map[p]:
                target_p = p
                target_threshold = threshold_map[p]
                break

        if target_p is not None:
            # Skip if this percentile already has an active event
            already_active = any(e.percentile <= target_p for e in active_events)
            if not already_active:
                # Parent = the active event at the nearest wider percentile zone.
                # (1% ⊂ 5% ⊂ 10% — use percentile containment, not price containment)
                potential_parents = [e for e in active_events if e.percentile > target_p]
                parent = min(potential_parents, key=lambda e: e.percentile) if potential_parents else None

                new_event = NPEvent(
                    percentile=target_p,
                    threshold=target_threshold,
                    start_date=current_date,
                    entry_price=current_price,
                    upline_id=parent.id if parent else None,
                )
                if parent:
                    parent.children_ids.append(new_event.id)
                active_events.append(new_event)

    # Finalize still-active events (unrecovered at end of data)
    for event in active_events:
        try:
            start_idx = prices.index.get_loc(event.start_date)
            min_idx = prices.index.get_loc(event.min_date)
            event.days_to_bottom = min_idx - start_idx
        except Exception:
            start_i = prices.index.searchsorted(event.start_date)
            min_i = prices.index.searchsorted(event.min_date)
            event.days_to_bottom = int(min_i - start_i)
        closed_events.append(event)

    # Calculate p_coverage (total descendant count) with memoization
    event_map = {e.id: e for e in closed_events}
    memo: dict = {}

    def get_coverage(e_id: str) -> int:
        if e_id in memo:
            return memo[e_id]
        if e_id not in event_map:
            return 0
        event = event_map[e_id]
        count = len(event.children_ids)
        for child_id in event.children_ids:
            count += get_coverage(child_id)
        memo[e_id] = count
        return count

    for event in closed_events:
        event.p_coverage = get_coverage(event.id)

    return closed_events


def get_detailed_current_status(
    price_series: pd.Series,
    signal_series: pd.Series,
    np_events: Optional[List[NPEvent]] = None,
    qr_threshold: int = MIN_RECOVERY_DAYS_THRESHOLD,
) -> dict:
    """
    Derive current-status fields entirely from the NP event tree.

    If np_events is provided (already computed by the caller) it is reused
    directly — no double computation.
    """
    current_price = float(price_series.iloc[-1])
    current_signal = float(signal_series.iloc[-1])
    rarity = (signal_series < current_signal).mean() * 100

    result = {
        "current_price": current_price,
        "current_signal": current_signal,
        "rarity": rarity,
        "ref_percentile": None,
        "entry_date": None,
        "entry_price": None,
        "entry_price_at_threshold": None,
        "historical_max_dd_of_zone": 0.0,
        "target_price": 0.0,
        "drawdown_from_current": None,
        "target_drawdown": None,
        "days_in_current_zone": None,
    }

    # Determine which zone the current signal sits in
    clean_signals = signal_series.dropna()
    threshold_map = {p: float(np.percentile(clean_signals, p)) for p in sorted(CALCULATE_PERCENTILES)}

    current_zone_p = None
    for p in sorted(CALCULATE_PERCENTILES):
        if current_signal <= threshold_map[p]:
            current_zone_p = p
            break

    if current_zone_p is None:
        return result  # signal not in any zone → safe

    result["ref_percentile"] = current_zone_p

    if np_events is None:
        np_events = calculate_np_events_tree(price_series, signal_series, CALCULATE_PERCENTILES)

    # Historical MAE distribution at this percentile (excludes quick recoveries)
    events_at_p = [e for e in np_events if e.percentile == current_zone_p]
    mae_values = [
        e.mae_pct for e in events_at_p
        if not (e.days_to_recover is not None and e.days_to_recover <= qr_threshold)
    ]
    if mae_values:
        worst_mae = max(mae_values)
        result["historical_max_dd_of_zone"] = -worst_mae / 100.0  # negative fraction

    # Find the most recent active (unrecovered) event at this zone
    active_at_p = [e for e in events_at_p if e.status == EventStatus.UNRECOVERED]
    if active_at_p:
        current_event = max(active_at_p, key=lambda e: e.start_date)
        entry_price = current_event.entry_price
        result["entry_date"] = current_event.start_date
        result["entry_price"] = entry_price
        result["entry_price_at_threshold"] = entry_price

        if mae_values:
            target_price = entry_price * (1 + result["historical_max_dd_of_zone"])
            result["target_price"] = target_price
            if current_price > 0:
                drawdown_from_current = (target_price / current_price) - 1
                result["drawdown_from_current"] = drawdown_from_current
                result["target_drawdown"] = drawdown_from_current

        try:
            start_idx = price_series.index.get_loc(current_event.start_date)
            end_idx = len(price_series) - 1
            result["days_in_current_zone"] = end_idx - start_idx + 1
        except Exception:
            start_i = price_series.index.searchsorted(current_event.start_date)
            result["days_in_current_zone"] = len(price_series) - start_i

    return result
