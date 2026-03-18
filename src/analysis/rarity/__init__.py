"""NP event detection, percentiles, and rarity analysis."""
from src.analysis.rarity.events import NPEvent, EventStatus, calculate_np_events_tree
from src.shared.stats import calculate_factor_percentiles
from src.analysis.rarity.compute import get_detailed_current_status

__all__ = [
    "NPEvent",
    "EventStatus",
    "calculate_np_events_tree",
    "calculate_factor_percentiles",
    "get_detailed_current_status",
]


"""
The data flow becomes obvious at a glance:

  events.py  →  compute.py  →  tables.py
                            →  charts.py
                            →  info_blocks.py
                            →  report.py

"""