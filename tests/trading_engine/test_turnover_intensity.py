from datetime import date, timedelta
from decimal import Decimal
import math

import pandas as pd
import pytest

from trading_engine.activity import (
    analyze_turnover_intensity,
    turnover_intensity_factor_series,
)
from trading_engine.types import TradingActivityObservation


START = date(2026, 1, 1)


def observation(
    offset: int,
    total_value: Decimal | float | int,
    market_cap: Decimal | float | int,
) -> TradingActivityObservation:
    return TradingActivityObservation(
        session=START + timedelta(days=offset),
        total_value=total_value,
        market_cap=market_cap,
    )


def test_turnover_intensity_uses_prior_twenty_sessions_and_population_std() -> None:
    observations = tuple(
        observation(index, total_value=index + 1, market_cap=1)
        for index in range(21)
    )

    result = analyze_turnover_intensity(observations)

    assert result.formula_version == "turnover_intensity_v1"
    assert result.baseline_sessions == 20
    assert len(result.points) == 21
    assert result.points[19].intensity == 20.0
    assert result.points[19].baseline is None
    assert result.points[19].anomaly_score is None
    assert result.points[19].unavailable_reason == "insufficient_history"
    assert result.points[20].intensity == 21.0
    assert result.points[20].baseline == pytest.approx(10.5)
    assert result.points[20].anomaly_score == pytest.approx(
        (21.0 - 10.5) / math.sqrt(33.25),
    )
    assert result.points[20].unavailable_reason is None


@pytest.mark.parametrize(
    ("total_value", "market_cap", "reason"),
    [
        (10, 0, "non_positive_market_cap"),
        (10, -1, "non_positive_market_cap"),
        (10, float("inf"), "invalid_market_cap"),
        (10, Decimal("NaN"), "invalid_market_cap"),
        (float("nan"), 100, "invalid_total_value"),
        (Decimal("Infinity"), 100, "invalid_total_value"),
        (-1, 100, "invalid_total_value"),
    ],
)
def test_turnover_intensity_marks_invalid_current_observations_unavailable(
    total_value: Decimal | float | int,
    market_cap: Decimal | float | int,
    reason: str,
) -> None:
    points = analyze_turnover_intensity((observation(0, total_value, market_cap),)).points

    assert points[0].intensity is None
    assert points[0].baseline is None
    assert points[0].anomaly_score is None
    assert points[0].unavailable_reason == reason


def test_turnover_intensity_rejects_invalid_prior_window() -> None:
    observations = [observation(index, index + 1, 1) for index in range(21)]
    observations[7] = observation(7, 8, 0)

    point = analyze_turnover_intensity(tuple(observations)).points[-1]

    assert point.intensity == 21.0
    assert point.baseline is None
    assert point.anomaly_score is None
    assert point.unavailable_reason == "invalid_baseline_window"


def test_turnover_intensity_rejects_zero_baseline_variance() -> None:
    observations = tuple(
        observation(index, total_value=10 if index < 20 else 12, market_cap=100)
        for index in range(21)
    )

    point = analyze_turnover_intensity(observations).points[-1]

    assert point.intensity == pytest.approx(0.12)
    assert point.baseline == pytest.approx(0.1)
    assert point.anomaly_score is None
    assert point.unavailable_reason == "zero_baseline_variance"


@pytest.mark.parametrize(
    "observations",
    [
        (observation(0, 1, 10), observation(0, 2, 10)),
        (observation(1, 1, 10), observation(0, 2, 10)),
    ],
)
def test_turnover_intensity_requires_strict_chronological_order(
    observations: tuple[TradingActivityObservation, ...],
) -> None:
    with pytest.raises(ValueError, match="strictly increasing"):
        analyze_turnover_intensity(observations)


def test_turnover_intensity_requires_positive_baseline_sessions() -> None:
    with pytest.raises(ValueError, match="baseline_sessions"):
        analyze_turnover_intensity((observation(0, 1, 10),), baseline_sessions=0)


def test_factor_series_exposes_only_next_session_values() -> None:
    analysis = analyze_turnover_intensity(tuple(
        observation(index, total_value=(index + 1) * 10, market_cap=100)
        for index in range(4)
    ))

    factor = turnover_intensity_factor_series(analysis)

    assert factor.name == "turnover_intensity_v1_lag1"
    assert factor.metadata == {
        "formula_version": "turnover_intensity_v1",
        "baseline_sessions": 20,
        "lag_sessions": 1,
    }
    assert list(factor.values.index) == list(pd.to_datetime([
        START + timedelta(days=1),
        START + timedelta(days=2),
        START + timedelta(days=3),
    ]))
    assert factor.values.tolist() == pytest.approx([0.1, 0.2, 0.3])


def test_factor_series_does_not_bridge_an_unavailable_prior_session() -> None:
    analysis = analyze_turnover_intensity((
        observation(0, 10, 100),
        observation(1, 10, 0),
        observation(2, 30, 100),
    ))

    factor = turnover_intensity_factor_series(analysis)

    assert list(factor.values.index) == [pd.Timestamp(START + timedelta(days=1))]
    assert factor.values.iloc[0] == pytest.approx(0.1)
