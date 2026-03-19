"""Ensemble strategy — weighted average of multiple sub-strategies."""
from __future__ import annotations

import pandas as pd

from trading_engine.types import PriceFrame, RegimeSeries, Strategy
from trading_engine.strategy.base import BaseStrategy


class EnsembleStrategy(BaseStrategy):
    """Meta-strategy: weighted average of N sub-strategy weight outputs.

    Implements the Strategy Protocol.
    Trades are generated from the averaged weight transitions only —
    not from the individual sub-strategy trades.
    """

    def __init__(
        self,
        strategies: list[Strategy],
        strategy_weights: list[float] | None = None,
    ):
        if not strategies:
            raise ValueError("EnsembleStrategy requires at least one sub-strategy")

        self.strategies = strategies

        if strategy_weights is None:
            # Equal weight by default
            self.strategy_weights = [1.0 / len(strategies)] * len(strategies)
        else:
            if len(strategy_weights) != len(strategies):
                raise ValueError(
                    f"Got {len(strategy_weights)} weights for "
                    f"{len(strategies)} strategies"
                )
            total = sum(strategy_weights)
            self.strategy_weights = [w / total for w in strategy_weights]

    def _compute_weights(
        self,
        symbols: list[str],
        prices: dict[str, PriceFrame],
        regime: RegimeSeries | None = None,
    ) -> pd.DataFrame:
        combined: pd.DataFrame | None = None

        for strategy, sw in zip(self.strategies, self.strategy_weights):
            output = strategy.compute(symbols, prices, regime)
            weighted = output.weights * sw

            if combined is None:
                combined = weighted
            else:
                combined = combined.add(weighted, fill_value=0.0)

        if combined is None:
            return pd.DataFrame()

        return combined.clip(-1.0, 1.0)
