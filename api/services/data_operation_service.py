"""Preview and validate collection- or instrument-scoped data operations."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Literal

from api.market_data_config import SUPPORTED_UNIVERSES
from api.instrument_data_routing import (
    InstrumentDataRoute,
    UnsupportedInstrumentRouteError,
    resolve_instrument_data_route,
)
from api.market_sessions import latest_completed_venue_session
from api.repositories.data_operation_repository import (
    DataOperationInstrumentRecord,
    DataOperationRepository,
    DataOperationScopeRecord,
    DataOperationScopeType,
)
from api.repositories.instrument_routing_repository import (
    InstrumentRoutingRepository,
)


DataOperationDataset = Literal["prices", "fundamentals"]
PriceCoverageStatus = Literal["current", "stale", "missing"]


class UnknownDataOperationScopeError(ValueError):
    pass


@dataclass(frozen=True)
class DataOperationPreview:
    scope_type: DataOperationScopeType
    scope_id: str
    scope_name: str
    dataset: DataOperationDataset
    instrument_count: int
    eligible_count: int
    current_count: int
    stale_count: int
    missing_count: int
    unsupported_count: int
    can_run: bool
    message: str
    execution_route: str | None


@dataclass(frozen=True)
class InstrumentPriceCoverage:
    instrument_id: int
    symbol: str
    instrument_type: str
    venue_code: str | None
    price_basis: str
    first_stored_session: date | None
    last_stored_session: date | None
    expected_session: date
    stored_sessions: int
    expected_sessions_behind: int | None
    coverage_status: PriceCoverageStatus
    coverage_source: str | None
    coverage_fetched_at: datetime | None
    last_attempted_through: date | None
    last_returned_through: date | None
    refresh_outcome: str | None
    refresh_source: str | None
    last_checked_at: datetime | None
    refresh_detail: str | None


@dataclass(frozen=True)
class InstrumentPriceCoveragePage:
    scope_type: DataOperationScopeType
    scope_id: str
    scope_name: str
    total: int
    offset: int
    limit: int
    current_count: int
    stale_count: int
    missing_count: int
    checked_no_new_bar_count: int
    failed_count: int
    instruments: tuple[InstrumentPriceCoverage, ...]


class DataOperationService:
    def __init__(
        self,
        repository: DataOperationRepository,
        routing_repository: InstrumentRoutingRepository,
    ) -> None:
        self._repository = repository
        self._routing_repository = routing_repository

    def preview(
        self,
        scope_type: DataOperationScopeType,
        scope_id: str,
        dataset: DataOperationDataset,
        *,
        now: datetime | None = None,
    ) -> DataOperationPreview:
        scope = self._repository.get_scope(scope_type, scope_id)
        if scope is None:
            raise UnknownDataOperationScopeError(
                f"Unknown {scope_type}: {scope_id}"
            )
        routes = self._routes(scope)
        eligible = tuple(
            row
            for row in scope.instruments
            if _eligible(row, routes.get(row.id), dataset)
        )
        current = now or datetime.now(UTC)
        current_count = sum(
            row.last_date is not None
            and row.last_date >= _expected_session(routes[row.id], current)
            for row in eligible
        )
        missing_count = sum(row.last_date is None for row in eligible)
        stale_count = len(eligible) - current_count - missing_count
        can_run, message, execution_route = _execution(
            scope, dataset, eligible, routes
        )
        return DataOperationPreview(
            scope_type=scope.scope_type,
            scope_id=scope.scope_id,
            scope_name=scope.name,
            dataset=dataset,
            instrument_count=len(scope.instruments),
            eligible_count=len(eligible),
            current_count=current_count,
            stale_count=stale_count,
            missing_count=missing_count,
            unsupported_count=len(scope.instruments) - len(eligible),
            can_run=can_run,
            message=message,
            execution_route=execution_route,
        )

    def price_coverage(
        self,
        scope_type: DataOperationScopeType,
        scope_id: str,
        *,
        offset: int = 0,
        limit: int = 50,
        now: datetime | None = None,
    ) -> InstrumentPriceCoveragePage:
        scope = self._repository.get_scope(scope_type, scope_id)
        if scope is None:
            raise UnknownDataOperationScopeError(
                f"Unknown {scope_type}: {scope_id}"
            )
        current = now or datetime.now(UTC)
        routes = self._routes(scope)
        rows = tuple(
            _price_coverage(row, routes.get(row.id), current)
            for row in scope.instruments
        )
        page = rows[offset:offset + limit]
        return InstrumentPriceCoveragePage(
            scope_type=scope.scope_type,
            scope_id=scope.scope_id,
            scope_name=scope.name,
            total=len(rows),
            offset=offset,
            limit=limit,
            current_count=sum(row.coverage_status == "current" for row in rows),
            stale_count=sum(row.coverage_status == "stale" for row in rows),
            missing_count=sum(row.coverage_status == "missing" for row in rows),
            checked_no_new_bar_count=sum(
                row.refresh_outcome == "checked_no_new_bar" for row in rows
            ),
            failed_count=sum(row.refresh_outcome == "failed" for row in rows),
            instruments=page,
        )

    def _routes(
        self, scope: DataOperationScopeRecord
    ) -> dict[int, InstrumentDataRoute]:
        metadata = self._routing_repository.get_instrument_routes_metadata(
            tuple(row.id for row in scope.instruments)
        )
        routes: dict[int, InstrumentDataRoute] = {}
        for row in metadata:
            try:
                routes[row.instrument_id] = resolve_instrument_data_route(row)
            except UnsupportedInstrumentRouteError:
                continue
        return routes


def _eligible(
    instrument: DataOperationInstrumentRecord,
    route: InstrumentDataRoute | None,
    dataset: DataOperationDataset,
) -> bool:
    if route is None:
        return False
    if dataset == "fundamentals":
        return route.fundamental_adapter is not None
    return True


def _expected_session(
    route: InstrumentDataRoute, now: datetime
):
    return latest_completed_venue_session(now, route.schedule)


def _price_coverage(
    instrument: DataOperationInstrumentRecord,
    route: InstrumentDataRoute | None,
    now: datetime,
) -> InstrumentPriceCoverage:
    expected = (
        _expected_session(route, now)
        if route is not None else now.astimezone(UTC).date() - timedelta(days=1)
    )
    if instrument.last_date is None:
        coverage_status: PriceCoverageStatus = "missing"
        sessions_behind = None
    elif instrument.last_date >= expected:
        coverage_status = "current"
        sessions_behind = 0
    else:
        coverage_status = "stale"
        sessions_behind = _expected_sessions_between(
            instrument.last_date,
            expected,
            weekdays_only=(
                route is not None
                and route.schedule.trading_calendar_code != "CRYPTO_24_7"
            ),
        )
    return InstrumentPriceCoverage(
        instrument_id=instrument.id,
        symbol=instrument.symbol,
        instrument_type=instrument.instrument_type,
        venue_code=instrument.venue_code,
        price_basis=instrument.price_basis,
        first_stored_session=instrument.first_date,
        last_stored_session=instrument.last_date,
        expected_session=expected,
        stored_sessions=instrument.row_count,
        expected_sessions_behind=sessions_behind,
        coverage_status=coverage_status,
        coverage_source=instrument.coverage_source,
        coverage_fetched_at=instrument.coverage_fetched_at,
        last_attempted_through=instrument.attempted_through,
        last_returned_through=instrument.returned_through,
        refresh_outcome=instrument.refresh_outcome,
        refresh_source=instrument.selected_source or instrument.primary_source,
        last_checked_at=instrument.attempted_at,
        refresh_detail=instrument.refresh_detail,
    )


def _expected_sessions_between(
    last_stored_session: date,
    expected_session: date,
    *,
    weekdays_only: bool,
) -> int:
    if last_stored_session >= expected_session:
        return 0
    if not weekdays_only:
        return (expected_session - last_stored_session).days
    cursor = last_stored_session + timedelta(days=1)
    count = 0
    while cursor <= expected_session:
        if cursor.weekday() < 5:
            count += 1
        cursor += timedelta(days=1)
    return count


def _execution(
    scope: DataOperationScopeRecord,
    dataset: DataOperationDataset,
    eligible: tuple[DataOperationInstrumentRecord, ...],
    routes: dict[int, InstrumentDataRoute],
) -> tuple[bool, str, str | None]:
    if not scope.instruments:
        return False, "This collection has no active instruments.", None
    if not eligible:
        return False, f"No instruments support {dataset} updates.", None
    adapters = {routes[row.id].price_adapter for row in eligible}
    all_equities = all(
        routes[row.id].fundamental_adapter is not None for row in eligible
    )
    execution_route = next(iter(adapters)) if len(adapters) == 1 else None
    if scope.scope_type == "universe":
        if scope.scope_id not in SUPPORTED_UNIVERSES or not all_equities:
            return (
                False,
                "Bulk updates are not enabled for this universe; select an exact instrument.",
                None,
            )
        return True, f"Ready to update {len(eligible)} eligible instruments.", execution_route
    if scope.scope_type == "watchlist":
        if dataset == "fundamentals":
            return False, "Watchlist fundamentals updates are not enabled yet.", None
        if not all_equities or execution_route not in {"yfinance", "vnstock_data"}:
            return (
                False,
                "Bulk watchlist updates currently require only US equities or only VN equities.",
                None,
            )
        return True, f"Ready to update {len(eligible)} watchlist instruments.", execution_route
    if dataset == "fundamentals":
        return False, "Single-instrument fundamentals updates are not enabled yet.", None
    return True, "Ready to update this instrument's canonical price history.", execution_route
