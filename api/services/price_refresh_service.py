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
from api.services.price_history_service import DEFAULT_PRICE_BASIS


RefreshMode = Literal["incremental", "full"]
INCREMENTAL_OVERLAP_DAYS = 7


class PriceRefreshError(ValueError):
    pass


@dataclass(frozen=True)
class PriceRefreshPlan:
    universe: str
    requested_starts: dict[str, date]
    reused_symbols: tuple[str, ...]


@dataclass(frozen=True)
class PriceRefreshWriteResult:
    input_rows: int
    rejected_rows: int
    stored_rows: int


@dataclass(frozen=True)
class PriceRefreshAttempt:
    ticker: str
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
        symbols: list[str],
        *,
        full_start: date,
        end: date,
        mode: RefreshMode,
        already_refreshed: set[str] | None = None,
    ) -> PriceRefreshPlan:
        normalized, market = self._resolve_universe(universe)
        if full_start > end:
            raise PriceRefreshError("Refresh start date must not be after end date")
        if mode not in ("incremental", "full"):
            raise PriceRefreshError(f"Unsupported refresh mode: {mode}")
        normalized_symbols = tuple(dict.fromkeys(
            symbol.upper().strip() for symbol in symbols if symbol.strip()
        ))
        skipped_overlap = already_refreshed or set()
        coverage = {
            row.ticker: row
            for row in self._repository.list_symbol_coverages(
                market, normalized_symbols, DEFAULT_PRICE_BASIS[market]
            )
        }
        refresh_states = {
            row.ticker: row
            for row in self._repository.list_refresh_states(
                market, normalized_symbols, DEFAULT_PRICE_BASIS[market]
            )
        }
        expected_latest = _latest_expected_session(end, market)
        requested: dict[str, date] = {}
        reused: list[str] = []
        for symbol in normalized_symbols:
            if symbol in skipped_overlap:
                reused.append(symbol)
                continue
            existing = coverage.get(symbol)
            refresh_state = refresh_states.get(symbol)
            if mode == "full" or existing is None:
                requested[symbol] = full_start
            elif existing.last_date >= expected_latest:
                reused.append(symbol)
            elif (
                refresh_state is not None
                and refresh_state.attempted_through >= expected_latest
                and refresh_state.outcome == "checked_no_new_bar"
            ):
                reused.append(symbol)
            else:
                requested[symbol] = max(
                    full_start,
                    existing.last_date - timedelta(days=INCREMENTAL_OVERLAP_DAYS),
                )
        return PriceRefreshPlan(
            universe=normalized,
            requested_starts=requested,
            reused_symbols=tuple(reused),
        )

    def store_frames(
        self,
        universe: str,
        frames: list[pd.DataFrame],
        *,
        source: str,
        fetched_at: datetime,
    ) -> PriceRefreshWriteResult:
        normalized, market = self._resolve_universe(universe)
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
        currency = "VND" if market == "VN" else "USD"
        price_scale = 1_000 if market == "VN" else 1
        records = (
            PriceBarWriteRecord(
                market=market,
                ticker=str(row.symbol),
                trading_date=row.date,
                open=float(row.open),
                high=float(row.high),
                low=float(row.low),
                close=float(row.close),
                volume=float(row.volume) if not pd.isna(row.volume) else None,
                currency=currency,
                price_scale=price_scale,
                price_basis=DEFAULT_PRICE_BASIS[market],
                source=source,
                fetched_at=fetched_at,
            )
            for row in clean.itertuples(index=False)
        )
        stored_rows = self._repository.upsert_bars(records)
        return PriceRefreshWriteResult(
            input_rows=input_rows,
            rejected_rows=rejected_rows,
            stored_rows=stored_rows,
        )

    def record_attempts(
        self,
        universe: str,
        attempts: list[PriceRefreshAttempt],
    ) -> int:
        _, market = self._resolve_universe(universe)
        records: list[PriceRefreshStateWriteRecord] = []
        for attempt in attempts:
            if attempt.attempted_at.tzinfo is None:
                raise PriceRefreshError("Refresh attempted_at must be timezone-aware")
            if attempt.returned_through and attempt.returned_through > attempt.attempted_through:
                raise PriceRefreshError(
                    "Refresh returned_through must not exceed attempted_through"
                )
            records.append(PriceRefreshStateWriteRecord(
                market=market,
                ticker=attempt.ticker.upper().strip(),
                price_basis=DEFAULT_PRICE_BASIS[market],
                attempted_through=attempt.attempted_through,
                returned_through=attempt.returned_through,
                outcome=attempt.outcome,
                primary_source=attempt.primary_source,
                selected_source=attempt.selected_source,
                detail=attempt.detail,
                attempted_at=attempt.attempted_at,
            ))
        return self._repository.upsert_refresh_states(records)

    def _resolve_universe(self, universe: str) -> tuple[str, str]:
        normalized = universe.upper().strip()
        market = self._repository.get_universe_market(normalized)
        if market not in DEFAULT_PRICE_BASIS:
            raise PriceRefreshError(f"Unknown price universe: {universe}")
        return normalized, market


def _latest_expected_session(end: date, market: str) -> date:
    # The application operates in Asia/Ho_Chi_Minh. A US session with the same
    # local calendar date has not completed yet, while a VN session may have.
    expected = end - timedelta(days=1) if market == "US" else end
    while expected.weekday() >= 5:
        expected -= timedelta(days=1)
    return expected
