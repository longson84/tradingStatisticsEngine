"""Portfolio dataclasses — wraps position results.

Note: No page is wired to this module yet. See TODOS.md → TODO-001.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pandas as pd

from src.position.trade import Trade


@dataclass
class PositionResult:
    """Trades + equity + metadata for one position."""
    ticker: str
    strategy_name: str
    trades: List[Trade]
    equity: pd.Series
    metadata: Dict = field(default_factory=dict)


@dataclass
class Portfolio:
    """Collection of position results. Currently holds 1 position; designed to scale to N."""
    positions: List[PositionResult] = field(default_factory=list)

    @property
    def equity(self) -> Optional[pd.Series]:
        """Aggregate equity curve. For 1 position, pass-through."""
        if not self.positions:
            return None
        if len(self.positions) == 1:
            return self.positions[0].equity
        # Future: weighted combination for multi-position
        combined = None
        for pos in self.positions:
            if combined is None:
                combined = pos.equity.copy()
            else:
                combined = combined.add(pos.equity, fill_value=0)
        return combined
