"""New-low episode analysis.

This is an event study, not a continuous factor.  It finds the first strict
break below a prior N-session closing low, ignores repeated lower lows until
the pre-break close is recovered, and then summarizes the episode outcomes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd

from trading_engine.event_analysis.episode_engine import (
    TriggerEpisode,
    analyze_trigger_episodes,
)
from trading_engine.types import InsufficientDataError, PriceFrame


@dataclass
class NewLowForwardStats:
    horizon: int
    count: int
    return_percentiles: dict[int, float]
    max_down_percentiles: dict[int, float]


@dataclass
class NewLowEpisode:
    start_date: date
    start_price: float
    recovery_level: float
    recovered: bool
    recovery_date: date | None
    recovery_sessions: int | None
    ignored_new_lows: int
    low_date: date
    low_price: float
    days_to_low: int
    max_down_pct: float
    current_return_pct: float | None = None
    forward_returns: dict[int, float | None] = field(default_factory=dict)
    forward_max_down: dict[int, float | None] = field(default_factory=dict)


@dataclass
class NewLowCurrentEpisode:
    start_date: date
    start_price: float
    recovery_level: float
    current_date: date
    current_price: float
    current_down_pct: float
    current_return_pct: float
    max_down_pct: float
    sessions_elapsed: int
    ignored_new_lows: int
    low_date: date
    low_price: float
    days_to_low: int
    recovery_needed_pct: float
    max_down_percentile: float
    ignored_lows_percentile: float
    duration_percentile: float


@dataclass
class NewLowAnalysisResult:
    symbol: str
    first_date: date
    last_date: date
    total_bars: int
    latest_price: float
    lookback_sessions: int
    quick_recovery_sessions: int
    raw_new_low_bars: int
    kept_episodes: int
    completed_episodes: int
    active_episodes: int
    quick_ignored_episodes: int
    total_ignored_new_lows: int
    max_down_percentiles: dict[int, float]
    recovery_session_percentiles: dict[int, float]
    ignored_new_low_percentiles: dict[int, float]
    current: NewLowCurrentEpisode | None
    forward_stats: list[NewLowForwardStats]
    episodes: list[NewLowEpisode]
    time_series: pd.DataFrame


def analyze_new_low_episodes(
    prices: PriceFrame,
    lookback_sessions: int = 50,
    quick_recovery_sessions: int = 2,
    forward_horizons: list[int] | None = None,
) -> NewLowAnalysisResult:
    """Analyze strict new-low episodes for one symbol.

    Trigger:
        close[t] < min(close[t-lookback_sessions:t])

    Recovery:
        close >= close[t-1], where t is the original episode trigger.

    Quick filter:
        recovered episodes with recovery_sessions <= quick_recovery_sessions
        are discarded.
    """
    if forward_horizons is None:
        forward_horizons = [5, 10, 20, 50, 100, 150, 200]
    if lookback_sessions < 2:
        raise ValueError("lookback_sessions must be at least 2")
    if quick_recovery_sessions < 0:
        raise ValueError("quick_recovery_sessions must be non-negative")

    close = prices.data["close"].dropna().astype(float)
    if len(close) <= lookback_sessions:
        raise InsufficientDataError(
            f"Need more than {lookback_sessions} bars for new-low analysis, got {len(close)}"
        )

    prior_low = close.shift(1).rolling(lookback_sessions).min()
    is_new_low = close < prior_low

    idx = close.index
    trigger_result = analyze_trigger_episodes(
        close=close,
        trigger=is_new_low,
        start_i=lookback_sessions,
        quick_recovery_sessions=quick_recovery_sessions,
        forward_horizons=forward_horizons,
        discard_quick_recoveries=True,
    )
    episodes = _build_public_episodes(trigger_result.episodes)
    completed = [e for e in episodes if e.recovered and e.recovery_sessions is not None]
    active = [e for e in episodes if not e.recovered]

    max_down_values = [e.max_down_pct for e in episodes]
    recovery_values = [float(e.recovery_sessions) for e in completed if e.recovery_sessions is not None]
    ignored_values = [float(e.ignored_new_lows) for e in episodes]

    current = None
    if active:
        current = _build_current_episode(
            active[-1],
            close=close,
            completed_recovery_values=recovery_values,
            max_down_values=max_down_values,
            ignored_values=ignored_values,
        )

    return NewLowAnalysisResult(
        symbol=prices.symbol,
        first_date=idx[0].date(),
        last_date=idx[-1].date(),
        total_bars=len(close),
        latest_price=float(close.iloc[-1]),
        lookback_sessions=lookback_sessions,
        quick_recovery_sessions=quick_recovery_sessions,
        raw_new_low_bars=trigger_result.raw_trigger_bars,
        kept_episodes=len(episodes),
        completed_episodes=len(completed),
        active_episodes=len(active),
        quick_ignored_episodes=trigger_result.quick_ignored_episodes,
        total_ignored_new_lows=sum(e.ignored_new_lows for e in episodes),
        max_down_percentiles=_percentiles(max_down_values, [50, 75, 90, 95, 100]),
        recovery_session_percentiles=_percentiles(recovery_values, [50, 75, 90, 95, 100]),
        ignored_new_low_percentiles=_percentiles(ignored_values, [50, 75, 90, 95, 100]),
        current=current,
        forward_stats=_build_forward_stats(episodes, forward_horizons),
        episodes=episodes,
        time_series=pd.DataFrame({
            "date": [ts.date() for ts in close.index],
            "close": close.values,
            "is_new_low": is_new_low.fillna(False).values.astype(bool),
        }),
    )


def _build_public_episodes(
    rows: list[TriggerEpisode],
) -> list[NewLowEpisode]:
    episodes: list[NewLowEpisode] = []
    for row in rows:
        episodes.append(NewLowEpisode(
            start_date=row.start_date,
            start_price=row.start_price,
            recovery_level=row.recovery_level,
            recovered=row.recovered,
            recovery_date=row.recovery_date,
            recovery_sessions=row.recovery_sessions,
            ignored_new_lows=row.ignored_triggers,
            low_date=row.low_date,
            low_price=row.low_price,
            days_to_low=row.days_to_low,
            max_down_pct=row.max_down_pct,
            current_return_pct=None,
            forward_returns=row.forward_returns,
            forward_max_down=row.forward_max_down,
        ))
    return episodes


def _build_current_episode(
    episode: NewLowEpisode,
    close: pd.Series,
    completed_recovery_values: list[float],
    max_down_values: list[float],
    ignored_values: list[float],
) -> NewLowCurrentEpisode:
    current_date = close.index[-1].date()
    current_price = float(close.iloc[-1])
    sessions_elapsed = len(close.loc[pd.Timestamp(episode.start_date):]) - 1
    current_return = _return_pct(episode.start_price, current_price)
    current_down = _drop_pct(episode.start_price, current_price)
    recovery_needed = _return_pct(current_price, episode.recovery_level)

    return NewLowCurrentEpisode(
        start_date=episode.start_date,
        start_price=episode.start_price,
        recovery_level=episode.recovery_level,
        current_date=current_date,
        current_price=current_price,
        current_down_pct=current_down,
        current_return_pct=current_return,
        max_down_pct=episode.max_down_pct,
        sessions_elapsed=sessions_elapsed,
        ignored_new_lows=episode.ignored_new_lows,
        low_date=episode.low_date,
        low_price=episode.low_price,
        days_to_low=episode.days_to_low,
        recovery_needed_pct=recovery_needed,
        max_down_percentile=_percentile_rank(max_down_values, episode.max_down_pct),
        ignored_lows_percentile=_percentile_rank(ignored_values, episode.ignored_new_lows),
        duration_percentile=_percentile_rank(completed_recovery_values, sessions_elapsed, weak=True),
    )


def _build_forward_stats(
    episodes: list[NewLowEpisode],
    forward_horizons: list[int],
) -> list[NewLowForwardStats]:
    stats: list[NewLowForwardStats] = []
    for horizon in forward_horizons:
        returns = [e.forward_returns[horizon] for e in episodes if e.forward_returns.get(horizon) is not None]
        max_down = [e.forward_max_down[horizon] for e in episodes if e.forward_max_down.get(horizon) is not None]
        stats.append(NewLowForwardStats(
            horizon=horizon,
            count=len(returns),
            return_percentiles=_percentiles([float(v) for v in returns], [5, 10, 15, 20, 25, 50, 75, 80, 90]),
            max_down_percentiles=_percentiles([float(v) for v in max_down], [50, 75, 90, 95]),
        ))
    return stats


def _return_pct(start: float, end: float) -> float:
    return (end / start - 1.0) * 100.0 if start > 0 else 0.0


def _drop_pct(start: float, low: float) -> float:
    return (start - low) / start * 100.0 if start > 0 else 0.0


def _percentiles(values: list[float], levels: list[int]) -> dict[int, float]:
    if not values:
        return {level: 0.0 for level in levels}
    return {level: float(np.percentile(values, level)) for level in levels}


def _percentile_rank(values: list[float], value: float, weak: bool = False) -> float:
    if not values:
        return 0.0
    arr = np.asarray(values, dtype=float)
    if weak:
        return float((arr <= value).sum() / len(arr) * 100.0)
    below = (arr < value).sum()
    equal = (arr == value).sum()
    if equal:
        return float((below + (equal + 1) / 2.0) / len(arr) * 100.0)
    return float(below / len(arr) * 100.0)
