"""Zone Rarity Analysis — how rare is this reading, and what happened every time we got here?

For each percentile zone (P1 … P50 by default):
  1. Find every historical entry (factor crosses below the zone threshold).
  2. Track: entry price, deepest price, recovery date, MAE%, days in zone.
  3. Aggregate per zone: count, quick-recovery rate, 5Y/10Y windows, MAE distribution.
  4. Build a parent-child hierarchy: an entry at zone P_k whose parent zone P_j
     was still active at entry time is a child of that P_j entry.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats
from typing import Literal

from trading_engine.constants import (
    DEFAULT_MAE_PERCENTILES,
    DEFAULT_QR_DAYS,
    DEFAULT_RARITY_ZONES,
)
from trading_engine.types import (
    InsufficientDataError,
    PriceFrame,
    RarityAnalysisResult,
    ZoneEntry,
    ZoneStats,
    FactorSeries,
)


# ── Internal working type ─────────────────────────────────────────────────────

@dataclass
class _Entry:
    """Mutable working entry used during construction before converting to ZoneEntry."""
    zone_pct: int
    start_date: date
    start_ts: pd.Timestamp
    entry_price: float
    entry_factor: float
    low_price: float
    low_date: date
    low_factor: float
    mae_pct: float
    days_to_low: int
    recovery_date: date | None
    days_to_recovery: int | None
    bars_elapsed: int | None
    is_active: bool
    is_quick_recovery: bool
    level: int = 0
    children_count: int = 0
    parent: "_Entry | None" = None


# ── Public API ────────────────────────────────────────────────────────────────

def zone_rarity_analysis(
    series: FactorSeries,
    prices: PriceFrame,
    zones: list[int] | None = None,
    quick_recovery_days: int = DEFAULT_QR_DAYS,
    mae_percentiles: list[int] | None = None,
    recovery_mode: Literal["factor", "price"] = "price",
) -> RarityAnalysisResult:
    """Run Zone Rarity Analysis for a single symbol and factor.

    Args:
        series: Pre-computed factor series (from factor.compute(prices)).
        prices: The matching PriceFrame (used for price-based MAE).
        zones: Percentile thresholds to analyze. Default: DEFAULT_RARITY_ZONES.
        quick_recovery_days: Sessions for a recovery to count as "quick".
        mae_percentiles: Which MAE percentile levels to report.
        recovery_mode:
            "factor": episode ends when factor exits the percentile zone.
            "price": episode ends when close recovers to the entry close.

    Returns:
        RarityAnalysisResult with zone stats table and full entry history.

    Raises:
        InsufficientDataError: If fewer than 2 data points after dropping NaNs.
    """
    if zones is None:
        zones = list(DEFAULT_RARITY_ZONES)
    if mae_percentiles is None:
        mae_percentiles = list(DEFAULT_MAE_PERCENTILES)
    if recovery_mode not in {"factor", "price"}:
        raise ValueError("recovery_mode must be 'factor' or 'price'")

    zones_asc = sorted(zones)  # [1, 5, 10, 15, 20, 25, 30, 40, 50]

    factor_vals = series.values.dropna()
    if len(factor_vals) < 2:
        raise InsufficientDataError(
            f"Need at least 2 data points for zone rarity analysis, "
            f"got {len(factor_vals)}"
        )

    # Align close prices to factor dates (factor may start later due to warmup)
    close = prices.data["close"].reindex(factor_vals.index).ffill()

    last_ts = factor_vals.index[-1]
    first_ts = factor_vals.index[0]
    five_yrs_ago = last_ts - pd.DateOffset(years=5)
    ten_yrs_ago = last_ts - pd.DateOffset(years=10)

    current_value = float(factor_vals.iloc[-1])
    current_price = float(close.iloc[-1])
    current_percentile = float(scipy_stats.percentileofscore(factor_vals, current_value))

    # Compute thresholds
    thresholds: dict[int, float] = {
        pct: float(np.percentile(factor_vals, pct)) for pct in zones_asc
    }

    # Determine current zone (most extreme zone the factor is currently inside)
    factor_current_zone: int | None = None
    for pct in zones_asc:  # ascending: stops at most extreme satisfied
        if current_value <= thresholds[pct]:
            factor_current_zone = pct
            break

    # Find all entries per zone
    entries_by_zone: dict[int, list[_Entry]] = {}
    for pct in zones_asc:
        entries_by_zone[pct] = _find_zone_entries(
            factor_vals,
            close,
            thresholds[pct],
            pct,
            quick_recovery_days,
            recovery_mode,
        )

    # When the factor gaps through multiple zone thresholds in a single bar,
    # keep only the most extreme (minimum zone_pct) entry for that bar.
    # E.g. if the factor drops from above P25 to below P15 in one session,
    # only the P15 entry is kept — P20 and P25 are discarded.
    entries_by_zone = _filter_same_day_breaches(entries_by_zone)

    # Assign levels and parent references
    _assign_levels(entries_by_zone, zones_asc)

    if recovery_mode == "price":
        active_entries = [
            e for entries in entries_by_zone.values() for e in entries if e.is_active
        ]
        current_zone = min((e.zone_pct for e in active_entries), default=None)
    else:
        current_zone = factor_current_zone

    # Build zone stats
    zone_stats: list[ZoneStats] = []
    for pct in zones_asc:
        zone_stats.append(_compute_zone_stats(
            pct=pct,
            threshold=thresholds[pct],
            entries=entries_by_zone[pct],
            five_yrs_ago=five_yrs_ago,
            ten_yrs_ago=ten_yrs_ago,
            mae_percentiles=mae_percentiles,
            is_current=(pct == current_zone),
        ))

    # Build display-ordered flat entry list
    display_entries = _build_display_order(entries_by_zone)

    # Current zone entry info
    zone_entry_date: date | None = None
    zone_entry_price: float | None = None
    sessions_in_zone = 0
    max_potential_drop_pct = 0.0

    if current_zone is not None:
        for e in entries_by_zone[current_zone]:
            if e.is_active:
                zone_entry_date = e.start_date
                zone_entry_price = e.entry_price
                # Count sessions from entry to last bar (inclusive of entry day)
                sessions_in_zone = int(factor_vals.loc[e.start_ts:].count())
                # Worst historical drop for this zone
                cz_stats = next(s for s in zone_stats if s.zone_pct == current_zone)
                max_potential_drop_pct = cz_stats.mmae_pct
                break

    # For active entries, count bars from entry date to the last available bar
    for e in display_entries:
        if e.is_active:
            e.bars_elapsed = int(factor_vals.loc[e.start_ts:].count())

    # Convert _Entry objects to public ZoneEntry dataclasses
    public_entries = [_to_zone_entry(e) for e in display_entries]

    return RarityAnalysisResult(
        factor_name=series.name,
        symbol=prices.symbol,
        stats_date=last_ts.date(),
        first_date=first_ts.date(),
        last_date=last_ts.date(),
        total_bars=len(factor_vals),
        current_price=current_price,
        current_value=current_value,
        current_percentile=current_percentile,
        current_zone=current_zone,
        zone_entry_date=zone_entry_date,
        zone_entry_price=zone_entry_price,
        sessions_in_zone=sessions_in_zone,
        max_potential_drop_pct=max_potential_drop_pct,
        factor_context={},  # caller fills this in via factor.context(prices)
        zone_stats=zone_stats,
        entries=public_entries,
    )


# ── Private helpers ───────────────────────────────────────────────────────────

def _find_zone_entries(
    factor_vals: pd.Series,
    close: pd.Series,
    threshold: float,
    zone_pct: int,
    quick_recovery_days: int,
    recovery_mode: Literal["factor", "price"],
) -> list[_Entry]:
    """Find factor-triggered entries and recover them by factor or price."""
    in_zone = factor_vals <= threshold

    entries: list[_Entry] = []
    i = 0
    n = len(in_zone)

    while i < n:
        if not in_zone.iloc[i]:
            i += 1
            continue

        # Check it's a fresh entry (either first bar or wasn't in zone yesterday)
        if i > 0 and in_zone.iloc[i - 1]:
            i += 1
            continue

        # Start of a new zone stay
        entry_ts = in_zone.index[i]
        entry_price = float(close.iloc[i])
        entry_factor = float(factor_vals.iloc[i])

        # Find episode recovery.
        #
        # factor mode: the episode ends when the factor exits the percentile zone.
        #
        # price mode: New-Low-style behavior, the episode ends when close
        # returns to the entry close. Repeated threshold touches before that
        # recovery are part of the same episode.
        j = i + 1
        if recovery_mode == "factor":
            while j < n and in_zone.iloc[j]:
                j += 1
        else:
            while j < n and float(close.iloc[j]) < entry_price:
                j += 1

        recovered = j < n
        end_pos = j if recovered and recovery_mode == "price" else j - 1

        # Slice covering the episode. Price recovery includes the recovery bar,
        # matching the New-Low episode engine; factor recovery keeps the prior
        # contiguous-zone behavior.
        stay_close = close.iloc[i:end_pos + 1]
        stay_factor = factor_vals.iloc[i:end_pos + 1]

        low_price = float(stay_close.min())
        low_ts = stay_close.idxmin()
        low_date = low_ts.date()
        low_factor = float(stay_factor.min())
        days_to_low = int(stay_close.loc[:low_ts].count()) - 1

        mae_pct = (entry_price - low_price) / entry_price * 100 if entry_price > 0 else 0.0

        if recovered:
            recovery_ts = in_zone.index[j]
            days_to_recovery = j - i
            is_active = False
            is_qr = days_to_recovery <= quick_recovery_days
        else:
            recovery_ts = None
            days_to_recovery = None
            is_active = True
            is_qr = False

        entries.append(_Entry(
            zone_pct=zone_pct,
            start_date=entry_ts.date(),
            start_ts=entry_ts,
            entry_price=entry_price,
            entry_factor=entry_factor,
            low_price=low_price,
            low_date=low_date,
            low_factor=low_factor,
            mae_pct=round(mae_pct, 4),
            days_to_low=days_to_low,
            recovery_date=recovery_ts.date() if recovery_ts is not None else None,
            days_to_recovery=days_to_recovery,
            bars_elapsed=None,
            is_active=is_active,
            is_quick_recovery=is_qr,
        ))
        i = j

    return entries


def _assign_levels(
    entries_by_zone: dict[int, list[_Entry]],
    zones_asc: list[int],
) -> None:
    """Assign level and parent to every entry in-place.

    Zones are nested: P20 ⊂ P25 ⊂ P30 ⊂ P40 ⊂ P50 (for a left-tail factor).
    A new entry at zone P_k is a child of the most recent still-active entry
    at the immediately less extreme zone (next higher pct in our zone list).

    Level 0 = no parent zone was active at entry time.
    """
    # Build a lookup: zone_pct → entries sorted by start_date
    # We process all entries in chronological order and maintain
    # the "most recently started active entry" per zone.

    # Collect all entries sorted chronologically
    all_entries: list[_Entry] = []
    for pct in zones_asc:
        all_entries.extend(entries_by_zone[pct])
    all_entries.sort(key=lambda e: e.start_ts)

    # For each zone, track which entry was the last active one we started
    # (used to find parents when a deeper-zone entry begins)
    active_entry: dict[int, _Entry | None] = {pct: None for pct in zones_asc}

    for entry in all_entries:
        pct = entry.zone_pct
        pct_idx = zones_asc.index(pct)

        # Walk up the zone list to find the nearest active ancestor.
        # We skip intermediate zones that may have been filtered out (e.g. by the
        # same-day breach filter), so we can't rely on just the one-step-up neighbor.
        parent_candidate = None
        for parent_idx in range(pct_idx + 1, len(zones_asc)):
            candidate = active_entry.get(zones_asc[parent_idx])
            if candidate is not None:
                parent_still_active = (
                    candidate.recovery_date is None
                    or candidate.recovery_date > entry.start_date
                )
                if parent_still_active:
                    parent_candidate = candidate
                    break  # nearest (most extreme) active ancestor wins

        if parent_candidate is not None:
            entry.parent = parent_candidate
            entry.level = parent_candidate.level + 1
            # Propagate children count up the ancestor chain
            ancestor = parent_candidate
            while ancestor is not None:
                ancestor.children_count += 1
                ancestor = ancestor.parent

        # Register this entry as the active entry for its zone
        active_entry[pct] = entry


def _compute_zone_stats(
    pct: int,
    threshold: float,
    entries: list[_Entry],
    five_yrs_ago: pd.Timestamp,
    ten_yrs_ago: pd.Timestamp,
    mae_percentiles: list[int],
    is_current: bool,
) -> ZoneStats:
    """Aggregate statistics for all entries in one zone."""
    count = len(entries)
    qr_count = sum(1 for e in entries if e.is_quick_recovery)
    qr_pct = qr_count / count * 100 if count else 0.0

    count_5y = sum(1 for e in entries if pd.Timestamp(e.start_date) >= five_yrs_ago)
    qr_5y = sum(1 for e in entries if pd.Timestamp(e.start_date) >= five_yrs_ago and e.is_quick_recovery)
    count_10y = sum(1 for e in entries if pd.Timestamp(e.start_date) >= ten_yrs_ago)
    qr_10y = sum(1 for e in entries if pd.Timestamp(e.start_date) >= ten_yrs_ago and e.is_quick_recovery)

    completed = [e for e in entries if e.days_to_recovery is not None]
    avg_days = float(np.mean([e.days_to_recovery for e in completed])) if completed else 0.0

    non_qr = [e for e in entries if not e.is_quick_recovery]
    maes = [e.mae_pct for e in non_qr]
    mmae_pct = float(max(maes)) if maes else 0.0
    mae_by_percentile: dict[int, float] = {}
    for p in mae_percentiles:
        # MAE is stored as a positive drawdown magnitude. A "MAE P5" column is
        # therefore the threshold for the worst 5% of outcomes, i.e. the 95th
        # percentile of positive MAE values.
        mae_by_percentile[p] = float(np.percentile(maes, 100 - p)) if maes else 0.0

    return ZoneStats(
        zone_pct=pct,
        threshold_value=threshold,
        count=count,
        qr_count=qr_count,
        qr_pct=round(qr_pct, 2),
        count_5y=count_5y,
        qr_5y=qr_5y,
        count_10y=count_10y,
        qr_10y=qr_10y,
        avg_days=round(avg_days, 1),
        mmae_pct=round(mmae_pct, 4),
        mae_by_percentile={p: round(v, 4) for p, v in mae_by_percentile.items()},
        is_current_zone=is_current,
    )


def _filter_same_day_breaches(
    entries_by_zone: dict[int, list[_Entry]],
) -> dict[int, list[_Entry]]:
    """When multiple zones are first breached on the same bar, keep only the
    most extreme (minimum zone_pct).

    If the factor gaps from above P25 to below P15 in one session it creates
    entries for P25, P20, and P15 simultaneously.  Only P15 is meaningful —
    the others are just artefacts of the same price move seen through
    less-extreme lenses.
    """
    all_entries: list[_Entry] = [e for lst in entries_by_zone.values() for e in lst]

    # Group by start timestamp
    by_ts: dict[pd.Timestamp, list[_Entry]] = {}
    for e in all_entries:
        by_ts.setdefault(e.start_ts, []).append(e)

    to_remove: set[int] = set()
    for group in by_ts.values():
        if len(group) <= 1:
            continue
        min_pct = min(e.zone_pct for e in group)
        for e in group:
            if e.zone_pct != min_pct:
                to_remove.add(id(e))

    if not to_remove:
        return entries_by_zone

    return {
        pct: [e for e in lst if id(e) not in to_remove]
        for pct, lst in entries_by_zone.items()
    }


def _filter_first_touch_per_zone(
    entries_by_zone: dict[int, list[_Entry]],
) -> dict[int, list[_Entry]]:
    """Within each parent episode keep only the first touch of each deeper zone.

    Rule: if P30 is hit inside a P40 episode, recovers back above P30 (but stays
    inside P40), and then hits P30 again — the second P30 crossing is not a new
    entry.  Descendants of removed entries are also removed.

    Entries with no parent (standalone root episodes) are never removed by this
    step — the deduplication only applies within a shared parent episode.
    """
    all_entries: list[_Entry] = [e for lst in entries_by_zone.values() for e in lst]

    # Build parent-id → sorted children list
    parent_to_children: dict[int, list[_Entry]] = {}
    for e in all_entries:
        if e.parent is not None:
            parent_to_children.setdefault(id(e.parent), []).append(e)
    for lst in parent_to_children.values():
        lst.sort(key=lambda e: e.start_ts)

    to_remove: set[int] = set()

    def _mark_subtree(entry: _Entry) -> None:
        to_remove.add(id(entry))
        for child in parent_to_children.get(id(entry), []):
            _mark_subtree(child)

    def _deduplicate_children(entry: _Entry) -> None:
        seen_zones: set[int] = set()
        for child in parent_to_children.get(id(entry), []):
            if child.zone_pct in seen_zones:
                _mark_subtree(child)
            else:
                seen_zones.add(child.zone_pct)
                _deduplicate_children(child)

    for e in all_entries:
        if e.level == 0:
            _deduplicate_children(e)

    # Rebuild entries_by_zone without removed entries and recompute children_count
    filtered: dict[int, list[_Entry]] = {
        pct: [e for e in lst if id(e) not in to_remove]
        for pct, lst in entries_by_zone.items()
    }

    # Recompute children_count on all surviving entries
    surviving_ids: set[int] = {id(e) for lst in filtered.values() for e in lst}
    for lst in filtered.values():
        for e in lst:
            e.children_count = 0
    for lst in filtered.values():
        for e in lst:
            ancestor = e.parent
            while ancestor is not None and id(ancestor) in surviving_ids:
                ancestor.children_count += 1
                ancestor = ancestor.parent

    return filtered


def _build_display_order(entries_by_zone: dict[int, list[_Entry]]) -> list[_Entry]:
    """Return entries in display order: pre-order tree traversal, roots sorted
    descending by start_date (most recent first), children ascending.

    Active trees appear before completed trees within the same sort order.
    """
    all_entries: list[_Entry] = [
        e for entries in entries_by_zone.values() for e in entries
    ]

    # Build parent → children mapping
    children: dict[int, list[_Entry]] = {}
    for e in all_entries:
        pid = id(e.parent) if e.parent is not None else None
        if pid is not None:
            children.setdefault(pid, []).append(e)

    # Sort children ascending by start_date
    for lst in children.values():
        lst.sort(key=lambda e: e.start_ts)

    # Collect root entries (level 0)
    roots = [e for e in all_entries if e.level == 0]
    # Active roots first, then completed; within each group descending by start_date
    roots.sort(key=lambda e: (not e.is_active, -e.start_ts.value))

    result: list[_Entry] = []

    def traverse(entry: _Entry) -> None:
        result.append(entry)
        for child in children.get(id(entry), []):
            traverse(child)

    for root in roots:
        traverse(root)

    return result


def _to_zone_entry(e: _Entry) -> ZoneEntry:
    return ZoneEntry(
        zone_pct=e.zone_pct,
        start_date=e.start_date,
        entry_price=e.entry_price,
        entry_factor=e.entry_factor,
        low_price=e.low_price,
        low_date=e.low_date,
        low_factor=e.low_factor,
        mae_pct=e.mae_pct,
        days_to_low=e.days_to_low,
        recovery_date=e.recovery_date,
        days_to_recovery=e.days_to_recovery,
        bars_elapsed=e.bars_elapsed,
        is_active=e.is_active,
        is_quick_recovery=e.is_quick_recovery,
        level=e.level,
        children_count=e.children_count,
        parent_zone_pct=e.parent.zone_pct if e.parent else None,
        parent_start_date=e.parent.start_date if e.parent else None,
    )
