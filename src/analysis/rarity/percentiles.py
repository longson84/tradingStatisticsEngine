"""Signal percentile computation and current status derivation."""
from typing import List, Optional

import numpy as np
import pandas as pd

from src.shared.constants import CALCULATE_PERCENTILES, MIN_RECOVERY_DAYS_THRESHOLD
from src.analysis.rarity.events import EventStatus, NPEvent, calculate_np_events_tree


def calculate_signal_percentiles(signal_series: pd.Series, percentiles=CALCULATE_PERCENTILES) -> pd.DataFrame:
    """Return a DataFrame of signal threshold values at each percentile."""
    clean = signal_series.dropna()
    return pd.DataFrame([
        {"Percentile": p, "Threshold": np.percentile(clean, p)}
        for p in percentiles
    ])


def get_detailed_current_status(
    price_series: pd.Series,
    signal_series: pd.Series,
    np_events: Optional[List[NPEvent]] = None,
    qr_threshold: int = MIN_RECOVERY_DAYS_THRESHOLD,
) -> dict:
    """Derive current-status fields from the NP event tree."""
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

    clean_signals = signal_series.dropna()
    threshold_map = {p: float(np.percentile(clean_signals, p)) for p in sorted(CALCULATE_PERCENTILES)}

    current_zone_p = None
    for p in sorted(CALCULATE_PERCENTILES):
        if current_signal <= threshold_map[p]:
            current_zone_p = p
            break

    if current_zone_p is None:
        return result

    result["ref_percentile"] = current_zone_p

    if np_events is None:
        np_events = calculate_np_events_tree(price_series, signal_series, CALCULATE_PERCENTILES)

    events_at_p = [e for e in np_events if e.percentile == current_zone_p]
    mae_values = [
        e.mae_pct for e in events_at_p
        if not (e.days_to_recover is not None and e.days_to_recover <= qr_threshold)
    ]
    if mae_values:
        worst_mae = max(mae_values)
        result["historical_max_dd_of_zone"] = -worst_mae / 100.0

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
