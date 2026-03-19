"""BaseStrategy — abstract base for all strategy implementations.

Strategy implementations only need to override _compute_weights().
BaseStrategy.compute() auto-calls _compute_weights() then
weight_transitions_to_trades() — no duplication across implementations.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from trading_engine.types import (
    PriceFrame,
    RegimeSeries,
    StrategyOutput,
    StrategyOutputError,
)
from trading_engine.strategy.utils import weight_transitions_to_trades


class BaseStrategy(ABC):
    """Abstract base class for all strategies.

    Subclasses implement _compute_weights() only.
    The compute() method handles:
    1. Calling _compute_weights()
    2. Validating the output (no NaN)
    3. Converting weight transitions to Trade records
    """

    def compute(
        self,
        symbols: list[str],
        prices: dict[str, PriceFrame],
        regime: RegimeSeries | None = None,
    ) -> StrategyOutput:
        weights = self._compute_weights(symbols, prices, regime)

        # Validate: no NaN allowed in output
        if weights.isna().any().any():
            raise StrategyOutputError(
                f"{self.__class__.__name__} produced NaN in weight output. "
                f"This is never allowed — check your computation logic."
            )

        # Clamp to [-1, 1]
        weights = weights.clip(-1.0, 1.0)

        trades = weight_transitions_to_trades(weights, prices)
        return StrategyOutput(weights=weights, trades=trades)

    @abstractmethod
    def _compute_weights(
        self,
        symbols: list[str],
        prices: dict[str, PriceFrame],
        regime: RegimeSeries | None = None,
    ) -> pd.DataFrame:
        """Compute the weight matrix.

        Args:
            symbols: List of symbols to trade.
            prices: Dict mapping symbol -> PriceFrame.
            regime: Optional regime labels (from run_portfolio's regime_config).

        Returns:
            DataFrame of shape (time x symbols), values in [-1, 1].
            Index = DatetimeIndex, columns = symbol names.
        """
        ...
