"""DataFrame builders for rarity analysis display — no Streamlit."""
from typing import List

import pandas as pd

from src.shared.constants import CALCULATE_PERCENTILES, DATE_FORMAT_DISPLAY, MAE_PERCENTILES
from src.shared.fmt import fmt_pct, fmt_price
from src.analysis.rarity.events import EventStatus, NPEvent


def build_stats_df(
    np_stats: dict,
    indicator,
    current_status: dict,
) -> tuple[pd.DataFrame, int | None]:
    """Build the NP statistics summary table.

    Returns (DataFrame with _highlight column, highlight_p).
    """
    sorted_mae = sorted(MAE_PERCENTILES, reverse=True)

    current_rarity = current_status.get("rarity", 100) if current_status else 100
    candidates = [p for p in CALCULATE_PERCENTILES if p > current_rarity]
    highlight_p = min(candidates) if candidates else None

    rows = []
    for p in CALCULATE_PERCENTILES:
        stat = np_stats.get(p)
        if not stat:
            continue
        row = {
            "PCT": f"{p}%",
            "Signal": indicator.format_value(stat["threshold"]),
            "Count": stat["count"],
            "QR": stat["qr"],
            "QR %": fmt_pct(stat['qr_pct']),
            "5Y": f"{stat['count_5y']}/{stat['qr_5y']}",
            "10Y": f"{stat['count_10y']}/{stat['qr_10y']}",
            "Days": stat["total_days"],
            "MMAE %": fmt_pct(stat['mmae']),
            "_highlight": p == highlight_p,
        }
        for mp in sorted_mae:
            val = stat["mae_stats"].get(mp, 0)
            row[f"MAE-{mp}%"] = fmt_pct(val)
        rows.append(row)

    return pd.DataFrame(rows), highlight_p


def build_event_tree_df(np_events: List[NPEvent], qr_threshold: int) -> pd.DataFrame:
    """Walk the NPEvent tree and return a flat DataFrame."""
    rows: list = []

    def walk(event: NPEvent, level: int = 0) -> None:
        if event.days_to_recover is not None and event.days_to_recover <= qr_threshold:
            return

        unrecovered = event.status == EventStatus.UNRECOVERED
        prefix = "  " * level + ("└─ " if level > 0 else "")
        start_str = event.start_date.strftime(DATE_FORMAT_DISPLAY)

        rows.append({
            "Lv": level,
            "Start": prefix + start_str,
            "Zone": f"{event.percentile}%",
            "Entry": fmt_price(event.entry_price),
            "Low": fmt_price(event.min_price),
            "Low Date": event.min_date.strftime(DATE_FORMAT_DISPLAY),
            "MAE %": fmt_pct(event.mae_pct),
            "→ Low": event.days_to_bottom,
            "Recovery": event.recovery_date.strftime(DATE_FORMAT_DISPLAY) if event.recovery_date else "—",
            "→ Rec": str(event.days_to_recover) if event.days_to_recover is not None else "active",
            "Children": event.p_coverage,
            "_unrecovered": unrecovered,
        })

        children = sorted(
            [e for e in np_events if e.upline_id == event.id],
            key=lambda e: e.start_date,
        )
        for child in children:
            walk(child, level + 1)

    top_events = sorted(
        [e for e in np_events if e.upline_id is None],
        key=lambda e: e.start_date,
        reverse=True,
    )
    for event in top_events:
        walk(event)

    return pd.DataFrame(rows)
