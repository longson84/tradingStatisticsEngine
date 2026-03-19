"""Shared test fixtures for trading_engine tests.

All fixtures use deterministic synthetic data — no network calls.
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from trading_engine.types import (
    ExplainRecord,
    PriceFrame,
    Portfolio,
    RegimeSeries,
    StrategyOutput,
    Trade,
    WeightEvent,
)
from trading_engine.strategy.base import BaseStrategy

# Fixed seed for all synthetic data
RNG_SEED = 42


def make_price_frame(
    symbol: str,
    days: int = 500,
    start: str = "2020-01-01",
    trend: float = 0.0003,
    seed: int = RNG_SEED,
) -> PriceFrame:
    """Create deterministic synthetic OHLCV data."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start, periods=days, freq="B")

    returns = rng.normal(trend, 0.02, days)
    close = 100.0 * np.cumprod(1 + returns)
    noise = lambda scale: rng.normal(0, scale, days)

    df = pd.DataFrame(
        {
            "open": close * (1 + noise(0.004)),
            "high": close * (1 + abs(noise(0.008))),
            "low": close * (1 - abs(noise(0.008))),
            "close": close,
            "volume": rng.integers(1_000_000, 10_000_000, days).astype(float),
        },
        index=dates,
    )
    # Ensure high >= close >= low (synthetic noise can violate this)
    df["high"] = df[["open", "high", "close"]].max(axis=1)
    df["low"] = df[["open", "low", "close"]].min(axis=1)

    return PriceFrame(symbol=symbol, data=df, source="synthetic")


@pytest.fixture
def price_frame() -> PriceFrame:
    """Single symbol, 500 bars."""
    return make_price_frame("BTC-USD")


@pytest.fixture
def prices_dict() -> dict[str, PriceFrame]:
    """Three symbols, 500 bars each."""
    return {
        "AAPL": make_price_frame("AAPL", seed=42),
        "MSFT": make_price_frame("MSFT", seed=43),
        "GOOGL": make_price_frame("GOOGL", seed=44),
    }


@pytest.fixture
def prices_dict_small() -> dict[str, PriceFrame]:
    """Two symbols, 100 bars — for fast tests."""
    return {
        "AAA": make_price_frame("AAA", days=100, seed=10),
        "BBB": make_price_frame("BBB", days=100, seed=11),
    }


class _DeterministicStrategy(BaseStrategy):
    """Strategy that goes long every 20 days, exits after 10 days.
    Fully deterministic — output depends only on the date index.
    """

    def _compute_weights(self, symbols, prices, regime=None) -> pd.DataFrame:
        all_weights = {}
        for symbol in symbols:
            if symbol not in prices:
                continue
            idx = prices[symbol].data.index
            weights = pd.Series(0.0, index=idx)
            # Long (weight=1.0) for days 0-9, 20-29, 40-49, ...
            for i in range(len(idx)):
                cycle = i % 20
                if cycle < 10:
                    weights.iloc[i] = 1.0
            all_weights[symbol] = weights
        return pd.DataFrame(all_weights)


@pytest.fixture
def simple_strategy() -> _DeterministicStrategy:
    """Deterministic long signal every 20 days for predictable trade output."""
    return _DeterministicStrategy()


@pytest.fixture
def known_trades() -> list[Trade]:
    """Pre-built Trade list with exact return_pct for metric validation.

    5 trades: 3 wins (+10%, +20%, +5%), 2 losses (-5%, -15%)
    Win rate = 60%, avg return = (10+20+5-5-15)/5 = 3.0%
    """
    def _make(symbol, direction, ret, holding=10, entry_w=1.0):
        return Trade(
            symbol=symbol,
            direction=direction,
            entry_date=date(2021, 1, 1),
            entry_price=100.0,
            entry_weight=entry_w,
            exit_date=date(2021, 1, 11),
            exit_price=100.0 * (1 + ret / 100),
            weight_history=[WeightEvent(date=date(2021, 1, 1), weight=entry_w, price=100.0)],
            return_pct=ret,
            holding_days=holding,
            mae_pct=min(ret * 0.5, 0.0),
            mfe_pct=max(ret, 0.0),
            explain=None,
        )

    return [
        _make("AAA", "long", 10.0),
        _make("BBB", "long", 20.0),
        _make("AAA", "long", 5.0),
        _make("BBB", "long", -5.0),
        _make("AAA", "long", -15.0),
    ]
