"""Build canonical Universe statistics from current membership and stored prices."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

import pandas as pd

from api.repositories.data_operation_repository import DataOperationRepository
from api.repositories.universe_stats_repository import (
    UniverseStatsCloseQuery,
    UniverseStatsRepository,
)
from trading_engine.factor_analysis import calculate_universe_stats
from trading_engine.types import InsufficientDataError


UNIVERSE_STATS_WINDOW = 200
UNIVERSE_STATS_MINIMUM_COVERAGE = 0.5
UNIVERSE_STATS_HISTORY_YEARS = 10
UNIVERSE_STATS_FORMULA_VERSION = "universe-distance-v1"


@dataclass(frozen=True)
class UniverseStatsPointData:
    date: date
    median_distance_from_high: float
    median_distance_from_low: float
    eligible_count: int
    coverage_pct: float


@dataclass(frozen=True)
class UniverseStatsResultData:
    universe_code: str
    universe_name: str
    member_count: int
    instruments_with_history: int
    missing_history_count: int
    first_date: date
    last_date: date
    sources: tuple[str, ...]
    fetched_at: datetime
    points: tuple[UniverseStatsPointData, ...]


@dataclass(frozen=True)
class UniverseStatsErrorData:
    universe_code: str
    message: str


@dataclass(frozen=True)
class UniverseStatsRunData:
    results: tuple[UniverseStatsResultData, ...]
    errors: tuple[UniverseStatsErrorData, ...]


class UniverseStatsService:
    def __init__(
        self,
        scope_repository: DataOperationRepository,
        stats_repository: UniverseStatsRepository,
    ) -> None:
        self._scope_repository = scope_repository
        self._stats_repository = stats_repository

    def run(self, universe_codes: list[str]) -> UniverseStatsRunData:
        normalized_codes = tuple(dict.fromkeys(
            code.strip().upper() for code in universe_codes if code.strip()
        ))
        results: list[UniverseStatsResultData] = []
        errors: list[UniverseStatsErrorData] = []
        for code in normalized_codes:
            try:
                results.append(self._run_one(code))
            except (ValueError, InsufficientDataError) as exc:
                errors.append(UniverseStatsErrorData(code, str(exc)))
        return UniverseStatsRunData(tuple(results), tuple(errors))

    def _run_one(self, code: str) -> UniverseStatsResultData:
        scope = self._scope_repository.get_scope("universe", code)
        if scope is None:
            raise ValueError(f"Unknown Universe: {code}")
        if not scope.instruments:
            raise InsufficientDataError("Universe has no active instruments")

        covered = tuple(
            instrument for instrument in scope.instruments
            if instrument.last_date is not None and instrument.row_count > 0
        )
        if not covered:
            raise InsufficientDataError("Universe has no canonical stored price history")
        end = max(instrument.last_date for instrument in covered)
        assert end is not None
        display_start = (
            pd.Timestamp(end) - pd.DateOffset(years=UNIVERSE_STATS_HISTORY_YEARS)
        ).date()
        load_start = display_start - timedelta(days=UNIVERSE_STATS_WINDOW * 2)
        query = UniverseStatsCloseQuery(
            instrument_price_bases=tuple(
                (instrument.id, instrument.price_basis) for instrument in covered
            ),
            start=load_start,
            end=end,
        )

        values_by_id: dict[int, list[tuple[date, float]]] = {}
        sources: set[str] = set()
        fetched_at: datetime | None = None
        for row in self._stats_repository.iter_closes(query):
            values_by_id.setdefault(row.instrument_id, []).append(
                (row.trading_date, row.close)
            )
            sources.add(row.source)
            fetched_at = max(fetched_at, row.fetched_at) if fetched_at else row.fetched_at
        if not values_by_id or fetched_at is None:
            raise InsufficientDataError("Universe has no prices in the analysis range")

        closes = pd.concat(
            {
                instrument_id: pd.Series(
                    (value for _, value in values),
                    index=pd.DatetimeIndex(date_value for date_value, _ in values),
                    dtype=float,
                )
                for instrument_id, values in values_by_id.items()
            },
            axis=1,
        )
        calculated = calculate_universe_stats(
            closes,
            member_count=len(scope.instruments),
            window=UNIVERSE_STATS_WINDOW,
            minimum_coverage=UNIVERSE_STATS_MINIMUM_COVERAGE,
        )
        visible_index = calculated.median_distance_from_high.index >= pd.Timestamp(display_start)
        high = calculated.median_distance_from_high[visible_index]
        low = calculated.median_distance_from_low[visible_index]
        counts = calculated.eligible_count[visible_index]
        coverage = calculated.coverage_pct[visible_index]
        if high.empty:
            raise InsufficientDataError("Universe has no qualifying dates in the display range")
        points = tuple(
            UniverseStatsPointData(
                date=index.date(),
                median_distance_from_high=float(high.loc[index]),
                median_distance_from_low=float(low.loc[index]),
                eligible_count=int(counts.loc[index]),
                coverage_pct=float(coverage.loc[index]),
            )
            for index in high.index
        )
        return UniverseStatsResultData(
            universe_code=scope.scope_id,
            universe_name=scope.name,
            member_count=len(scope.instruments),
            instruments_with_history=len(values_by_id),
            missing_history_count=len(scope.instruments) - len(values_by_id),
            first_date=points[0].date,
            last_date=points[-1].date,
            sources=tuple(sorted(sources)),
            fetched_at=fetched_at,
            points=points,
        )
