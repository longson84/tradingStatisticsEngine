"""Provider-neutral capabilities derived from canonical Instrument metadata."""
from __future__ import annotations

from typing import Literal


InstrumentCapability = Literal[
    "foreign_flow", "proprietary_flow", "session_stats",
]
VN_EQUITY_VENUES = frozenset({"HOSE", "HNX", "UPCOM"})


def participant_flow_capability(participant_type: str) -> InstrumentCapability:
    return {
        "foreign": "foreign_flow",
        "proprietary": "proprietary_flow",
    }[participant_type]
