"""Versioned turnover-intensity analysis over stored session observations."""
from __future__ import annotations

import math
from statistics import fmean, pstdev

import pandas as pd

from trading_engine.types import (
    FactorSeries,
    NumericObservation,
    TradingActivityObservation,
    TurnoverIntensityAnalysis,
    TurnoverIntensityPoint,
    TurnoverIntensityUnavailableReason,
)


FORMULA_VERSION = "turnover_intensity_v1"


def analyze_turnover_intensity(
    observations: tuple[TradingActivityObservation, ...],
    baseline_sessions: int = 20,
) -> TurnoverIntensityAnalysis:
    """Compare each session's traded value with company market capitalization.

    Baseline and anomaly calculations use only the immediately preceding
    stored sessions, so the current observation never informs its own baseline.
    """
    if baseline_sessions < 1:
        raise ValueError("baseline_sessions must be at least 1")
    if any(
        current.session <= previous.session
        for previous, current in zip(observations, observations[1:], strict=False)
    ):
        raise ValueError("Trading activity sessions must be strictly increasing")

    ratios = tuple(_intensity(observation) for observation in observations)
    points: list[TurnoverIntensityPoint] = []
    for index, observation in enumerate(observations):
        intensity, current_reason = ratios[index]
        baseline: float | None = None
        anomaly: float | None = None
        reason = current_reason

        if index < baseline_sessions:
            reason = reason or "insufficient_history"
        else:
            window = ratios[index - baseline_sessions:index]
            if any(value is None for value, _ in window):
                reason = reason or "invalid_baseline_window"
            else:
                values = [value for value, _ in window if value is not None]
                baseline = fmean(values)
                standard_deviation = pstdev(values)
                if reason is None and standard_deviation == 0:
                    reason = "zero_baseline_variance"
                elif reason is None and intensity is not None:
                    anomaly = (intensity - baseline) / standard_deviation

        points.append(TurnoverIntensityPoint(
            session=observation.session,
            intensity=intensity,
            baseline=baseline,
            anomaly_score=anomaly,
            unavailable_reason=reason,
        ))

    return TurnoverIntensityAnalysis(
        formula_version=FORMULA_VERSION,
        baseline_sessions=baseline_sessions,
        points=tuple(points),
    )


def turnover_intensity_factor_series(
    analysis: TurnoverIntensityAnalysis,
) -> FactorSeries:
    """Expose intensity to factor/strategy consumers one session later."""
    raw = pd.Series(
        [point.intensity for point in analysis.points],
        index=pd.to_datetime([point.session for point in analysis.points]),
        dtype=float,
    )
    return FactorSeries(
        name=f"{analysis.formula_version}_lag1",
        values=raw.shift(1).dropna(),
        metadata={
            "formula_version": analysis.formula_version,
            "baseline_sessions": analysis.baseline_sessions,
            "lag_sessions": 1,
        },
    )


def _intensity(
    observation: TradingActivityObservation,
) -> tuple[float | None, TurnoverIntensityUnavailableReason | None]:
    total_value = _finite_float(observation.total_value)
    if total_value is None or total_value < 0:
        return None, "invalid_total_value"
    market_cap = _finite_float(observation.market_cap)
    if market_cap is None:
        return None, "invalid_market_cap"
    if market_cap <= 0:
        return None, "non_positive_market_cap"
    intensity = total_value / market_cap
    if not math.isfinite(intensity):
        return None, "invalid_market_cap"
    return intensity, None


def _finite_float(value: NumericObservation) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None
