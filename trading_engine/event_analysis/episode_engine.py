"""Generic trigger-to-recovery episode engine.

An episode starts when a boolean trigger is true and ends when price recovers
to the close immediately before the trigger bar. Repeated triggers in the same
episode are counted but ignored for episode creation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import pandas as pd


@dataclass
class TriggerEpisode:
    entry_i: int
    end_i: int
    start_date: date
    start_ts: pd.Timestamp
    start_price: float
    recovery_level: float
    recovered: bool
    recovery_date: date | None
    recovery_ts: pd.Timestamp | None
    recovery_sessions: int | None
    ignored_triggers: int
    low_i: int
    low_date: date
    low_ts: pd.Timestamp
    low_price: float
    days_to_low: int
    max_down_pct: float
    is_quick_recovery: bool
    forward_returns: dict[int, float | None] = field(default_factory=dict)
    forward_max_down: dict[int, float | None] = field(default_factory=dict)


@dataclass
class TriggerEpisodeResult:
    episodes: list[TriggerEpisode]
    raw_trigger_bars: int
    quick_ignored_episodes: int


def analyze_trigger_episodes(
    close: pd.Series,
    trigger: pd.Series,
    *,
    start_i: int = 1,
    quick_recovery_sessions: int = 0,
    forward_horizons: list[int] | None = None,
    discard_quick_recoveries: bool = False,
) -> TriggerEpisodeResult:
    """Convert a trigger series into price-recovery episodes."""
    if forward_horizons is None:
        forward_horizons = []
    if quick_recovery_sessions < 0:
        raise ValueError("quick_recovery_sessions must be non-negative")

    close = close.dropna().astype(float)
    trigger = trigger.reindex(close.index).fillna(False).astype(bool)
    idx = close.index
    n = len(close)
    i = max(0, start_i)
    episodes: list[TriggerEpisode] = []
    quick_ignored = 0

    while i < n:
        if not bool(trigger.iloc[i]):
            i += 1
            continue

        entry_i = i
        entry_ts = idx[entry_i]
        entry_price = float(close.iloc[entry_i])
        recovery_level = float(close.iloc[entry_i - 1]) if entry_i > 0 else entry_price

        j = entry_i + 1
        while j < n and float(close.iloc[j]) < recovery_level:
            j += 1

        recovered = j < n
        end_i = j if recovered else n - 1
        recovery_sessions = j - entry_i if recovered else None
        is_quick = recovered and recovery_sessions is not None and recovery_sessions <= quick_recovery_sessions

        if is_quick and discard_quick_recoveries:
            quick_ignored += 1
        else:
            episode_close = close.iloc[entry_i:end_i + 1]
            low_ts = episode_close.idxmin()
            low_i = int(idx.get_loc(low_ts))
            low_price = float(close.iloc[low_i])
            forward_returns, forward_max_down = _forward_metrics(
                close=close,
                entry_i=entry_i,
                entry_price=entry_price,
                forward_horizons=forward_horizons,
            )

            episodes.append(TriggerEpisode(
                entry_i=entry_i,
                end_i=end_i,
                start_date=entry_ts.date(),
                start_ts=entry_ts,
                start_price=entry_price,
                recovery_level=recovery_level,
                recovered=recovered,
                recovery_date=idx[j].date() if recovered else None,
                recovery_ts=idx[j] if recovered else None,
                recovery_sessions=recovery_sessions,
                ignored_triggers=int(trigger.iloc[entry_i + 1:end_i + 1].sum()),
                low_i=low_i,
                low_date=low_ts.date(),
                low_ts=low_ts,
                low_price=low_price,
                days_to_low=low_i - entry_i,
                max_down_pct=_drop_pct(entry_price, low_price),
                is_quick_recovery=bool(is_quick),
                forward_returns=forward_returns,
                forward_max_down=forward_max_down,
            ))

        i = j + 1 if recovered else n

    return TriggerEpisodeResult(
        episodes=episodes,
        raw_trigger_bars=int(trigger.sum()),
        quick_ignored_episodes=quick_ignored,
    )


def _forward_metrics(
    close: pd.Series,
    entry_i: int,
    entry_price: float,
    forward_horizons: list[int],
) -> tuple[dict[int, float | None], dict[int, float | None]]:
    n = len(close)
    forward_returns: dict[int, float | None] = {}
    forward_max_down: dict[int, float | None] = {}

    for horizon in forward_horizons:
        if entry_i + horizon < n:
            horizon_price = float(close.iloc[entry_i + horizon])
            path_low = float(close.iloc[entry_i:entry_i + horizon + 1].min())
            forward_returns[horizon] = _return_pct(entry_price, horizon_price)
            forward_max_down[horizon] = _drop_pct(entry_price, path_low)
        else:
            forward_returns[horizon] = None
            forward_max_down[horizon] = None

    return forward_returns, forward_max_down


def _return_pct(start: float, end: float) -> float:
    return (end / start - 1.0) * 100.0 if start > 0 else 0.0


def _drop_pct(start: float, low: float) -> float:
    return (start - low) / start * 100.0 if start > 0 else 0.0
