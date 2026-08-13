"""Preview and validate collection- or instrument-scoped data operations."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
import os
from typing import Literal

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
FUNDAMENTAL_REUSE_WINDOW = timedelta(hours=12)


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


@dataclass(frozen=True)
class DataOperationWorkGroup:
    adapter: str
    instrument_ids: tuple[int, ...]


@dataclass(frozen=True)
class DataOperationPlan:
    scope_type: DataOperationScopeType
    scope_id: str
    scope_name: str
    dataset: DataOperationDataset
    instrument_count: int
    eligible_count: int
    unsupported_count: int
    groups: tuple[DataOperationWorkGroup, ...]
    can_run: bool
    message: str


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
        plan, scope, routes = self._plan(scope_type, scope_id, dataset)
        eligible = tuple(
            row
            for row in scope.instruments
            if _eligible(row, routes.get(row.id), dataset)
        )
        current = now or datetime.now(UTC)
        if dataset == "fundamentals":
            current_count = sum(
                row.fundamental_fetched_at is not None
                and current - _as_utc(row.fundamental_fetched_at)
                <= FUNDAMENTAL_REUSE_WINDOW
                for row in eligible
            )
            missing_count = sum(
                row.fundamental_fetched_at is None for row in eligible
            )
        else:
            current_count = sum(
                row.last_date is not None
                and row.last_date >= _expected_session(routes[row.id], current)
                for row in eligible
            )
            missing_count = sum(row.last_date is None for row in eligible)
        stale_count = len(eligible) - current_count - missing_count
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
            can_run=plan.can_run,
            message=plan.message,
        )

    def plan(
        self,
        scope_type: DataOperationScopeType,
        scope_id: str,
        dataset: DataOperationDataset,
    ) -> DataOperationPlan:
        plan, _, _ = self._plan(scope_type, scope_id, dataset)
        return plan

    def _plan(
        self,
        scope_type: DataOperationScopeType,
        scope_id: str,
        dataset: DataOperationDataset,
    ) -> tuple[
        DataOperationPlan,
        DataOperationScopeRecord,
        dict[int, InstrumentDataRoute],
    ]:
        scope = self._repository.get_scope(scope_type, scope_id)
        if scope is None:
            raise UnknownDataOperationScopeError(
                f"Unknown {scope_type}: {scope_id}"
            )
        routes = self._routes(scope)
        grouped: dict[str, list[int]] = {}
        for instrument in scope.instruments:
            route = routes.get(instrument.id)
            adapter = _dataset_adapter(route, dataset)
            if adapter is not None:
                grouped.setdefault(adapter, []).append(instrument.id)
        groups = tuple(
            DataOperationWorkGroup(adapter, tuple(instrument_ids))
            for adapter, instrument_ids in sorted(grouped.items())
        )
        eligible_count = sum(len(group.instrument_ids) for group in groups)
        can_run, message = _execution(
            scope, dataset, groups, eligible_count
        )
        return DataOperationPlan(
            scope_type=scope.scope_type,
            scope_id=scope.scope_id,
            scope_name=scope.name,
            dataset=dataset,
            instrument_count=len(scope.instruments),
            eligible_count=eligible_count,
            unsupported_count=len(scope.instruments) - eligible_count,
            groups=groups,
            can_run=can_run,
            message=message,
        ), scope, routes

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


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


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


def _dataset_adapter(
    route: InstrumentDataRoute | None,
    dataset: DataOperationDataset,
) -> str | None:
    if route is None:
        return None
    return (
        route.fundamental_adapter
        if dataset == "fundamentals"
        else route.price_adapter
    )


def _execution(
    scope: DataOperationScopeRecord,
    dataset: DataOperationDataset,
    groups: tuple[DataOperationWorkGroup, ...],
    eligible_count: int,
) -> tuple[bool, str]:
    if not scope.instruments:
        return False, "This scope has no active instruments."
    if not eligible_count:
        return False, f"No instruments support {dataset} updates."
    oversized = tuple(
        (group.adapter, len(group.instrument_ids), _bulk_limit(dataset, group.adapter))
        for group in groups
        if len(group.instrument_ids) > _bulk_limit(dataset, group.adapter)
    )
    if oversized:
        details = ", ".join(
            f"{adapter} {count}/{limit}"
            for adapter, count, limit in oversized
        )
        return False, f"This operation exceeds configured adapter limits: {details}."
    unsupported = len(scope.instruments) - eligible_count
    adapters = ", ".join(group.adapter for group in groups)
    suffix = (
        f" {unsupported} unsupported instruments will be skipped."
        if unsupported else ""
    )
    return (
        True,
        f"Ready to update {eligible_count} instruments via {adapters}.{suffix}",
    )


def _bulk_limit(dataset: DataOperationDataset, adapter: str) -> int:
    defaults = {
        ("prices", "yfinance"): 5_000,
        ("prices", "vnstock_data"): 1_000,
        ("prices", "binance_spot"): 100,
        ("fundamentals", "yfinance"): 5_000,
        ("fundamentals", "vnstock_data"): 1_000,
    }
    default = defaults.get((dataset, adapter), 1)
    key = f"DATA_OPERATION_{dataset}_{adapter}_MAX_INSTRUMENTS".upper()
    try:
        value = int(os.getenv(key, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default
