"""NP event tree — detection and tree construction."""
import uuid
from enum import Enum
from typing import List, Optional

import numpy as np
import pandas as pd
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


def calculate_np_events_tree(
    price_series: pd.Series,
    factor_series: pd.Series,
    percentiles: list,
) -> List[NPEvent]:
    """Detect NP events using a tree structure."""
    common_idx = price_series.index.intersection(factor_series.index)
    if len(common_idx) < 2:
        return []

    prices = price_series.loc[common_idx]
    factors = factor_series.loc[common_idx]

    clean_factors = factor_series.dropna()
    threshold_map = {p: np.percentile(clean_factors, p) for p in percentiles}
    sorted_percentiles = sorted(percentiles)

    active_events: List[NPEvent] = []
    closed_events: List[NPEvent] = []

    for i in range(1, len(common_idx)):
        current_date = common_idx[i]
        current_price = prices.iloc[i]
        current_factor = factors.iloc[i]

        still_active = []
        for event in active_events:
            event.update_price(current_date, current_price)
            if current_price >= event.entry_price:
                event.close(current_date, prices)
                closed_events.append(event)
            else:
                still_active.append(event)
        active_events = still_active

        target_p = None
        target_threshold = None
        for p in sorted_percentiles:
            if current_factor <= threshold_map[p]:
                target_p = p
                target_threshold = threshold_map[p]
                break

        if target_p is not None:
            already_active = any(e.percentile <= target_p for e in active_events)
            if not already_active:
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
