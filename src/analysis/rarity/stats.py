"""NP statistics calculation — extracted from ReportGenerator."""
import numpy as np
import pandas as pd

from src.shared.constants import CALCULATE_PERCENTILES, MAE_PERCENTILES
from src.analysis.rarity.events import NPEvent


def calculate_np_stats(
    np_events: list[NPEvent],
    df: pd.DataFrame,
    qr_threshold: int,
) -> dict:
    """Calculate per-percentile NP statistics.

    Returns a dict keyed by percentile → stats dict (or None if no events).
    """
    stats = {}
    last_date = df.index[-1]
    date_5y = last_date - pd.DateOffset(years=5)
    date_10y = last_date - pd.DateOffset(years=10)

    for p in CALCULATE_PERCENTILES:
        events = [e for e in np_events if e.percentile == p]

        n_count = len(events)
        if n_count == 0:
            stats[p] = None
            continue

        qr_count = sum(1 for e in events if e.days_to_recover is not None and e.days_to_recover <= qr_threshold)

        count_5y = 0
        qr_5y = 0
        count_10y = 0
        qr_10y = 0

        for e in events:
            is_qr_event = e.days_to_recover is not None and e.days_to_recover <= qr_threshold

            if e.start_date >= date_5y:
                count_5y += 1
                if is_qr_event:
                    qr_5y += 1

            if e.start_date >= date_10y:
                count_10y += 1
                if is_qr_event:
                    qr_10y += 1

        total_days = 0
        mae_values = []

        for e in events:
            if e.days_to_recover is not None:
                total_days += e.days_to_recover
            else:
                last_idx = len(df) - 1
                start_idx = df.index.get_loc(e.start_date)
                total_days += last_idx - start_idx

            is_qr = e.days_to_recover is not None and e.days_to_recover <= qr_threshold
            if not is_qr:
                mae_values.append(e.mae_pct)

        mmae = max(mae_values) if mae_values else 0
        mae_percentiles_vals = {}
        if mae_values:
            for mp in MAE_PERCENTILES:
                mae_percentiles_vals[mp] = np.percentile(mae_values, mp)

        threshold = events[0].threshold if events else 0

        stats[p] = {
            "threshold": threshold,
            "count": n_count,
            "qr": qr_count,
            "qr_pct": (qr_count / n_count) * 100,
            "count_5y": count_5y,
            "qr_5y": qr_5y,
            "count_10y": count_10y,
            "qr_10y": qr_10y,
            "total_days": total_days,
            "mmae": mmae,
            "mae_stats": mae_percentiles_vals,
        }
    return stats
