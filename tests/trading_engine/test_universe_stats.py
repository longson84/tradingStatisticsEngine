from __future__ import annotations

import pandas as pd
import pytest

from trading_engine.factor_analysis.universe_stats import calculate_universe_stats
from trading_engine.types import InsufficientDataError


def test_universe_stats_calculates_median_distance_from_high_and_low():
    dates = pd.date_range("2026-01-01", periods=4, freq="D")
    closes = pd.DataFrame(
        {
            101: [10.0, 12.0, 8.0, 9.0],
            202: [20.0, 18.0, 24.0, 21.0],
        },
        index=dates,
    )

    result = calculate_universe_stats(
        closes,
        member_count=2,
        window=3,
        minimum_coverage=1.0,
    )

    assert list(result.median_distance_from_high.index) == list(dates[2:])
    assert result.median_distance_from_high.iloc[0] == pytest.approx(-16.6666667)
    assert result.median_distance_from_low.iloc[0] == pytest.approx(16.6666667)
    assert result.eligible_count.tolist() == [2, 2]
    assert result.coverage_pct.tolist() == [100.0, 100.0]


def test_universe_stats_forward_fills_only_after_first_observation():
    dates = pd.date_range("2026-01-01", periods=4, freq="D")
    closes = pd.DataFrame(
        {
            101: [10.0, None, 8.0, 9.0],
            202: [None, 20.0, 18.0, 24.0],
        },
        index=dates,
    )

    result = calculate_universe_stats(
        closes,
        member_count=2,
        window=2,
        minimum_coverage=0.5,
    )

    assert result.eligible_count.iloc[0] == 1
    assert result.median_distance_from_high.index[0] == dates[1]
    assert result.eligible_count.iloc[-1] == 2


def test_universe_stats_rejects_dates_below_current_membership_coverage():
    closes = pd.DataFrame(
        {101: [10.0, 11.0, 12.0]},
        index=pd.date_range("2026-01-01", periods=3, freq="D"),
    )

    with pytest.raises(InsufficientDataError, match="No date has 2 members"):
        calculate_universe_stats(
            closes,
            member_count=3,
            window=2,
            minimum_coverage=0.5,
        )
