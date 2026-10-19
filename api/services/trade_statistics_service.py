"""Read stored daily activity for an exact requested range without provider access."""
from __future__ import annotations

from dataclasses import dataclass, replace
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Literal

from api.instrument_data_routing import (
    InstrumentDataRoute,
    UnsupportedInstrumentRouteError,
    resolve_instrument_data_route,
)
from api.market_sessions import latest_completed_venue_session
from api.repositories.data_operation_repository import (
    DataOperationRepository,
    DataOperationScopeType,
)
from api.repositories.instrument_routing_repository import InstrumentRoutingRepository
from api.repositories.trade_statistics_repository import (
    DailyTradeStatisticRecord,
    TradeStatisticInstrumentRecord,
    TradeStatisticsRepository,
)
from trading_engine.activity import analyze_turnover_intensity
from trading_engine.types import (
    TradingActivityObservation,
    TurnoverIntensityAnalysis,
    TurnoverIntensityUnavailableReason,
)


TURNOVER_INTENSITY_BASELINE_SESSIONS = 20


class UnknownTradeStatisticsInstrumentError(ValueError):
    pass


class TradeStatisticsCapabilityError(ValueError):
    pass


class TradeStatisticsUnavailableError(ValueError):
    pass


class UnknownTradingActivityScopeError(ValueError):
    pass


@dataclass(frozen=True)
class TradeStatisticsData:
    instrument: TradeStatisticInstrumentRecord
    requested_start: date
    requested_end: date
    first_date: date
    last_date: date
    rows: tuple[DailyTradeStatisticRecord, ...]
    turnover_intensity: TurnoverIntensityAnalysis


TradingActivityScannerStatus = Literal[
    "current", "stale", "insufficient_history", "unavailable",
]
TradingActivityScannerUnavailableReason = (
    TurnoverIntensityUnavailableReason
    | Literal["unsupported_instrument", "no_stored_activity"]
)


@dataclass(frozen=True)
class TradingActivityScannerItem:
    instrument_id: int
    symbol: str
    display_name: str | None
    venue_code: str | None
    status: TradingActivityScannerStatus
    rank: int | None
    latest_session: date | None
    turnover_intensity: float | None
    baseline: float | None
    anomaly_score: float | None
    unavailable_reason: TradingActivityScannerUnavailableReason | None


@dataclass(frozen=True)
class TradingActivityScannerData:
    scope_type: Literal["universe", "watchlist"]
    scope_id: str
    scope_name: str
    target_session: date | None
    formula_version: str
    baseline_sessions: int
    counts: dict[TradingActivityScannerStatus, int]
    items: tuple[TradingActivityScannerItem, ...]


def resolve_trade_statistics_instrument(
    repository: TradeStatisticsRepository,
    routing_repository: InstrumentRoutingRepository,
    instrument_id: int,
) -> tuple[TradeStatisticInstrumentRecord, InstrumentDataRoute]:
    """Share canonical identity and capability validation across read/write paths."""
    instrument = repository.get_instrument(instrument_id)
    metadata = routing_repository.get_instrument_route_metadata(instrument_id)
    if instrument is None or metadata is None:
        raise UnknownTradeStatisticsInstrumentError(f"Unknown instrument: {instrument_id}")
    try:
        route = resolve_instrument_data_route(metadata)
    except UnsupportedInstrumentRouteError as exc:
        raise TradeStatisticsCapabilityError(
            f"Instrument {instrument_id} does not support trade_history"
        ) from exc
    if "trade_history" not in route.capabilities:
        raise TradeStatisticsCapabilityError(
            f"Instrument {instrument_id} does not support trade_history"
        )
    return instrument, route


class TradeStatisticsService:
    def __init__(
        self,
        repository: TradeStatisticsRepository,
        routing_repository: InstrumentRoutingRepository,
    ) -> None:
        self._repository = repository
        self._routing_repository = routing_repository

    def get_stored_range(
        self, instrument_id: int, start: date, end: date,
    ) -> TradeStatisticsData:
        if start > end:
            raise ValueError("start date must be on or before end date")
        instrument, _ = resolve_trade_statistics_instrument(
            self._repository, self._routing_repository, instrument_id,
        )
        rows = self._repository.list_rows(instrument_id, start, end)
        if not rows:
            raise TradeStatisticsUnavailableError(
                f"No stored daily trade statistics for instrument {instrument_id} "
                f"from {start} through {end}"
            )
        context_rows = self._repository.list_rows_before(
            instrument_id,
            before=start,
            limit=TURNOVER_INTENSITY_BASELINE_SESSIONS,
        )
        analysis = analyze_turnover_intensity(tuple(
            TradingActivityObservation(
                session=row.trading_date,
                total_value=row.total_value,
                market_cap=row.market_cap,
            )
            for row in (*context_rows, *rows)
        ))
        return TradeStatisticsData(
            instrument=instrument, requested_start=start, requested_end=end,
            first_date=rows[0].trading_date, last_date=rows[-1].trading_date,
            rows=rows,
            turnover_intensity=TurnoverIntensityAnalysis(
                formula_version=analysis.formula_version,
                baseline_sessions=analysis.baseline_sessions,
                points=analysis.points[len(context_rows):],
            ),
        )


class TradingActivityScannerService:
    """Rank stored activity for current members without accessing a provider."""

    def __init__(
        self,
        scope_repository: DataOperationRepository,
        activity_repository: TradeStatisticsRepository,
        routing_repository: InstrumentRoutingRepository,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._scope_repository = scope_repository
        self._activity_repository = activity_repository
        self._routing_repository = routing_repository
        self._clock = clock

    def scan(
        self, scope_type: DataOperationScopeType, scope_id: str,
    ) -> TradingActivityScannerData:
        if scope_type not in {"universe", "watchlist"}:
            raise ValueError("Trading activity scanner scope must be universe or watchlist")
        scope = self._scope_repository.get_scope(scope_type, scope_id)
        if scope is None:
            raise UnknownTradingActivityScopeError(
                f"Unknown {scope_type}: {scope_id}"
            )
        instrument_ids = tuple(instrument.id for instrument in scope.instruments)
        metadata = {
            row.instrument_id: row
            for row in self._routing_repository.get_instrument_routes_metadata(
                instrument_ids
            )
        }
        supported_routes = {}
        completed_sessions: dict[int, date] = {}
        now = self._clock()
        for instrument_id in instrument_ids:
            route_metadata = metadata.get(instrument_id)
            if route_metadata is None:
                continue
            try:
                route = resolve_instrument_data_route(route_metadata)
            except UnsupportedInstrumentRouteError:
                continue
            if "trade_history" not in route.capabilities:
                continue
            supported_routes[instrument_id] = route
            completed_sessions[instrument_id] = latest_completed_venue_session(
                now, route.schedule
            )

        supported_ids = tuple(
            instrument_id for instrument_id in instrument_ids
            if instrument_id in supported_routes
        )
        rows = ()
        if supported_ids:
            rows = self._activity_repository.list_recent_rows(
                supported_ids,
                through=max(completed_sessions.values()),
                limit_per_instrument=TURNOVER_INTENSITY_BASELINE_SESSIONS + 1,
            )
        grouped: dict[int, list[DailyTradeStatisticRecord]] = defaultdict(list)
        for row in rows:
            if row.trading_date <= completed_sessions[row.instrument_id]:
                grouped[row.instrument_id].append(row)
        target_session = max(
            (records[-1].trading_date for records in grouped.values() if records),
            default=None,
        )

        items = []
        for instrument in scope.instruments:
            records = grouped[instrument.id]
            if instrument.id not in supported_routes:
                items.append(self._scanner_item(
                    instrument, "unavailable", None,
                    unavailable_reason="unsupported_instrument",
                ))
                continue
            if not records:
                items.append(self._scanner_item(
                    instrument, "unavailable", None,
                    unavailable_reason="no_stored_activity",
                ))
                continue
            analysis = analyze_turnover_intensity(tuple(
                TradingActivityObservation(
                    session=row.trading_date,
                    total_value=row.total_value,
                    market_cap=row.market_cap,
                )
                for row in records
            ))
            point = analysis.points[-1]
            if point.session != target_session:
                status: TradingActivityScannerStatus = "stale"
            elif point.unavailable_reason == "insufficient_history":
                status = "insufficient_history"
            elif point.intensity is None:
                status = "unavailable"
            else:
                status = "current"
            items.append(self._scanner_item(
                instrument, status, point.session,
                turnover_intensity=point.intensity,
                baseline=point.baseline,
                anomaly_score=point.anomaly_score,
                unavailable_reason=point.unavailable_reason,
            ))

        ranked = sorted(
            (item for item in items if item.status == "current"),
            key=lambda item: (-(item.turnover_intensity or 0), item.symbol),
        )
        ranks = {item.instrument_id: rank for rank, item in enumerate(ranked, 1)}
        items = [replace(item, rank=ranks.get(item.instrument_id)) for item in items]
        status_order = {"current": 0, "stale": 1, "insufficient_history": 2, "unavailable": 3}
        items.sort(key=lambda item: (
            status_order[item.status], item.rank or 0, item.symbol,
        ))
        counts: dict[TradingActivityScannerStatus, int] = {
            status: sum(item.status == status for item in items)
            for status in ("current", "stale", "insufficient_history", "unavailable")
        }
        return TradingActivityScannerData(
            scope_type=scope_type,
            scope_id=scope.scope_id,
            scope_name=scope.name,
            target_session=target_session,
            formula_version="turnover_intensity_v1",
            baseline_sessions=TURNOVER_INTENSITY_BASELINE_SESSIONS,
            counts=counts,
            items=tuple(items),
        )

    @staticmethod
    def _scanner_item(
        instrument,
        status: TradingActivityScannerStatus,
        latest_session: date | None,
        *,
        turnover_intensity: float | None = None,
        baseline: float | None = None,
        anomaly_score: float | None = None,
        unavailable_reason: TradingActivityScannerUnavailableReason | None = None,
    ) -> TradingActivityScannerItem:
        return TradingActivityScannerItem(
            instrument_id=instrument.id,
            symbol=instrument.symbol,
            display_name=instrument.display_name,
            venue_code=instrument.venue_code,
            status=status,
            rank=None,
            latest_session=latest_session,
            turnover_intensity=turnover_intensity,
            baseline=baseline,
            anomaly_score=anomaly_score,
            unavailable_reason=unavailable_reason,
        )
