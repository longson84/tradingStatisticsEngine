"""Read stored exact-period session statistics without provider access."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from api.instrument_data_routing import (
    UnsupportedInstrumentRouteError,
    resolve_instrument_data_route,
)
from api.repositories.instrument_routing_repository import InstrumentRoutingRepository
from api.repositories.session_statistics_repository import (
    SessionStatisticInstrumentRecord,
    SessionStatisticSnapshotRecord,
    SessionStatisticsRepository,
)
from api.session_statistics import (
    SESSION_STATISTIC_METRICS,
    SessionStatisticMetricDefinition,
)


class UnknownSessionStatisticsInstrumentError(ValueError):
    pass


class SessionStatisticsCapabilityError(ValueError):
    pass


class SessionStatisticsUnavailableError(ValueError):
    pass


@dataclass(frozen=True)
class SessionStatisticValue:
    definition: SessionStatisticMetricDefinition
    value: Decimal


@dataclass(frozen=True)
class SessionStatisticsData:
    instrument: SessionStatisticInstrumentRecord
    snapshot: SessionStatisticSnapshotRecord
    metrics: tuple[SessionStatisticValue, ...]


class SessionStatisticsService:
    def __init__(
        self,
        repository: SessionStatisticsRepository,
        routing_repository: InstrumentRoutingRepository,
    ) -> None:
        self._repository = repository
        self._routing_repository = routing_repository

    def get_stored_snapshot(
        self, instrument_id: int, period_start: date, period_end: date
    ) -> SessionStatisticsData:
        if period_start > period_end:
            raise ValueError("start date must be on or before end date")
        instrument = self._repository.get_instrument(instrument_id)
        metadata = self._routing_repository.get_instrument_route_metadata(instrument_id)
        if instrument is None or metadata is None:
            raise UnknownSessionStatisticsInstrumentError(
                f"Unknown instrument: {instrument_id}"
            )
        try:
            route = resolve_instrument_data_route(metadata)
        except UnsupportedInstrumentRouteError as exc:
            raise SessionStatisticsCapabilityError(
                f"Instrument {instrument_id} does not support session_stats"
            ) from exc
        if "session_stats" not in route.capabilities:
            raise SessionStatisticsCapabilityError(
                f"Instrument {instrument_id} does not support session_stats"
            )
        snapshot = self._repository.get_latest_snapshot(
            instrument_id, period_start, period_end
        )
        if snapshot is None:
            raise SessionStatisticsUnavailableError(
                f"No stored session statistics for instrument {instrument_id} "
                f"from {period_start} through {period_end}"
            )
        values = {metric.code: metric.value for metric in snapshot.metrics}
        return SessionStatisticsData(
            instrument=instrument,
            snapshot=snapshot,
            metrics=tuple(
                SessionStatisticValue(definition=definition, value=values[definition.code])
                for definition in SESSION_STATISTIC_METRICS
            ),
        )
