"""Provider-neutral capabilities derived from canonical Instrument metadata."""
from __future__ import annotations

from typing import Literal


InstrumentCapability = Literal["foreign_flow"]
VN_EQUITY_VENUES = frozenset({"HOSE", "HNX", "UPCOM"})
