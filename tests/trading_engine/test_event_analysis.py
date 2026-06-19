"""Tests for price event-analysis modules."""
from __future__ import annotations

import pandas as pd

from trading_engine.event_analysis import analyze_new_low_episodes
from trading_engine.types import PriceFrame


def _prices(closes: list[float]) -> PriceFrame:
    idx = pd.date_range("2024-01-01", periods=len(closes), freq="D")
    return PriceFrame(
        symbol="TEST",
        source="test",
        data=pd.DataFrame({
            "open": closes,
            "high": closes,
            "low": closes,
            "close": closes,
            "volume": [1] * len(closes),
        }, index=idx),
    )


def test_new_low_episode_ignores_lower_lows_until_recovery():
    prices = _prices([
        10, 11, 12, 13, 14,
        9, 8, 7, 8, 14,
        6, 7, 8, 10,
    ])

    result = analyze_new_low_episodes(
        prices,
        lookback_sessions=5,
        quick_recovery_sessions=0,
        forward_horizons=[2],
    )

    assert result.raw_new_low_bars == 4
    assert result.kept_episodes == 2
    first, second = result.episodes
    assert first.start_price == 9
    assert first.recovery_level == 14
    assert first.ignored_new_lows == 2
    assert first.low_price == 7
    assert first.recovery_date is not None
    assert second.start_price == 6


def test_quick_recovery_episode_is_discarded():
    prices = _prices([10, 11, 12, 13, 14, 9, 15, 8, 7, 15])

    result = analyze_new_low_episodes(
        prices,
        lookback_sessions=5,
        quick_recovery_sessions=2,
        forward_horizons=[2],
    )

    assert result.quick_ignored_episodes == 2
    assert result.kept_episodes == 0
