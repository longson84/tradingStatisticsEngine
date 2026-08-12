"""Incremental price-refresh planning and persistence use cases."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal

import numpy as np
import pandas as pd

from api.repositories.price_bar_repository import (
    PriceBarRefreshRepository,
    PriceBarWriteRecord,
    PriceRefreshStateWriteRecord,
)


RefreshMode = Literal["incremental", "full"]
INCREMENTAL_OVERLAP_DAYS = 7


class PriceRefreshError(ValueError):
    pass


@dataclass(frozen=True)
class PriceRefreshPlan:
    universe: str
    requested_starts: dict[int, date]
    reused_instrument_ids: tuple[int, ...]


@dataclass(frozen=True)
class PriceRefreshTarget:
    instrument_id: int
    canonical_symbol: str
    provider_symbol: str
    price_adapter: str
    price_basis: str
    currency: str
    price_scale: int


@dataclass(frozen=True)
class PriceRefreshWriteResult:
    input_rows: int
    rejected_rows: int
    stored_rows: int


@dataclass(frozen=True)
class PriceRefreshAttempt:
    instrument_id: int
    price_basis: str
    attempted_through: date
    returned_through: date | None
    outcome: Literal["current", "checked_no_new_bar", "failed"]
    primary_source: str
    selected_source: str | None
    attempted_at: datetime
    detail: str | None = None


class PriceRefreshService:
    def __init__(self, repository: PriceBarRefreshRepository):
        self._repository = repository

    def plan(
        self,
        universe: str,
        targets: list[PriceRefreshTarget],
        *,
        full_start: date,
        end: date,
        mode: RefreshMode,
        already_refreshed: set[int] | None = None,
    ) -> PriceRefreshPlan:
        normalized = universe.upper().strip()
        if full_start > end:
            raise PriceRefreshError("Refresh start date must not be after end date")
        if mode not in ("incremental", "full"):
            raise PriceRefreshError(f"Unsupported refresh mode: {mode}")
        normalized_targets = tuple(dict.fromkeys(targets))
        if not normalized_targets:
            return PriceRefreshPlan(normalized, {}, ())
        route_signatures = {
            (target.price_adapter, target.price_basis)
            for target in normalized_targets
        }
        if len(route_signatures) > 1:
            raise PriceRefreshError(
                f"{normalized} refresh targets must use one data route"
            )
        instrument_ids = tuple(target.instrument_id for target in normalized_targets)
        skipped_overlap = already_refreshed or set()
        coverage = {
            row.instrument_id: row
            for row in self._repository.list_instrument_coverages(
                instrument_ids, normalized_targets[0].price_basis
            )
        }
        refresh_states = {
            row.instrument_id: row
            for row in self._repository.list_instrument_refresh_states(
                instrument_ids, normalized_targets[0].price_basis
            )
        }
        expected_latest = end
        requested: dict[int, date] = {}
        reused: list[int] = []
        for target in normalized_targets:
            instrument_id = target.instrument_id
            if instrument_id in skipped_overlap:
                reused.append(instrument_id)
                continue
            existing = coverage.get(instrument_id)
            refresh_state = refresh_states.get(instrument_id)
            if mode == "full" or existing is None:
                requested[instrument_id] = full_start
            elif existing.last_date >= expected_latest:
                reused.append(instrument_id)
            elif (
                refresh_state is not None
                and refresh_state.attempted_through >= expected_latest
                and refresh_state.outcome == "checked_no_new_bar"
            ):
                reused.append(instrument_id)
            else:
                requested[instrument_id] = max(
                    full_start,
                    existing.last_date - timedelta(days=INCREMENTAL_OVERLAP_DAYS),
                )
        return PriceRefreshPlan(
            universe=normalized,
            requested_starts=requested,
            reused_instrument_ids=tuple(reused),
        )

    def store_frames(
        self,
        scope_name: str,
        frames: list[pd.DataFrame],
        *,
        targets_by_provider_symbol: dict[str, PriceRefreshTarget],
        source: str,
        fetched_at: datetime,
    ) -> PriceRefreshWriteResult:
        normalized = scope_name.upper().strip()
        if fetched_at.tzinfo is None:
            raise PriceRefreshError("Refresh fetched_at must be timezone-aware")
        if not frames:
            return PriceRefreshWriteResult(0, 0, 0)
        data = pd.concat(frames, ignore_index=True)
        required = {"symbol", "date", "open", "high", "low", "close"}
        missing = required - set(data.columns)
        if missing:
            raise PriceRefreshError(
                f"{normalized} refresh rows are missing columns: {sorted(missing)}"
            )
        data = data.copy()
        data["symbol"] = data["symbol"].astype(str).str.upper().str.strip()
        unknown_symbols = sorted(
            set(data["symbol"]) - set(targets_by_provider_symbol)
        )
        if unknown_symbols:
            raise PriceRefreshError(
                f"{normalized} refresh returned unknown symbols: {unknown_symbols}"
            )
        data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.date
        for column in ("open", "high", "low", "close", "volume"):
            if column not in data:
                data[column] = np.nan
            data[column] = pd.to_numeric(data[column], errors="coerce")
        input_rows = len(data)
        finite_prices = np.isfinite(data[["open", "high", "low", "close"]]).all(axis=1)
        finite_volume = data["volume"].isna() | np.isfinite(data["volume"])
        valid = (
            data["symbol"].ne("")
            & data["date"].notna()
            & finite_prices
            & finite_volume
            & data[["open", "high", "low", "close"]].gt(0).all(axis=1)
            & data["high"].ge(data["low"])
            & (data["volume"].isna() | data["volume"].ge(0))
        )
        clean = (
            data.loc[valid]
            .sort_values(["symbol", "date"])
            .drop_duplicates(["symbol", "date"], keep="last")
        )
        rejected_rows = input_rows - len(clean)
        records = (
            PriceBarWriteRecord(
                instrument_id=target.instrument_id,
                trading_date=row.date,
                open=float(row.open),
                high=float(row.high),
                low=float(row.low),
                close=float(row.close),
                volume=float(row.volume) if not pd.isna(row.volume) else None,
                currency=target.currency,
                price_scale=target.price_scale,
                price_basis=target.price_basis,
                source=source,
                fetched_at=fetched_at,
            )
            for row in clean.itertuples(index=False)
            for target in (targets_by_provider_symbol[str(row.symbol)],)
        )
        stored_rows = self._repository.upsert_bars(records)
        return PriceRefreshWriteResult(
            input_rows=input_rows,
            rejected_rows=rejected_rows,
            stored_rows=stored_rows,
        )

    def record_attempts(
        self,
        attempts: list[PriceRefreshAttempt],
    ) -> int:
        records: list[PriceRefreshStateWriteRecord] = []
        for attempt in attempts:
            if attempt.attempted_at.tzinfo is None:
                raise PriceRefreshError("Refresh attempted_at must be timezone-aware")
            if attempt.returned_through and attempt.returned_through > attempt.attempted_through:
                raise PriceRefreshError(
                    "Refresh returned_through must not exceed attempted_through"
                )
            records.append(PriceRefreshStateWriteRecord(
                instrument_id=attempt.instrument_id,
                price_basis=attempt.price_basis,
                attempted_through=attempt.attempted_through,
                returned_through=attempt.returned_through,
                outcome=attempt.outcome,
                primary_source=attempt.primary_source,
                selected_source=attempt.selected_source,
                detail=attempt.detail,
                attempted_at=attempt.attempted_at,
            ))
        return self._repository.upsert_refresh_states(records)
