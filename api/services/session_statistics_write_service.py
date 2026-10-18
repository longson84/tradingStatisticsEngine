"""Validate and persist one exact-period session-statistics snapshot."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Mapping

from api.instrument_data_routing import (
    UnsupportedInstrumentRouteError,
    resolve_instrument_data_route,
)
from api.repositories.instrument_routing_repository import InstrumentRoutingRepository
from api.repositories.session_statistics_repository import (
    SessionStatisticSnapshotWrite,
    SessionStatisticsRepository,
)
from api.services.session_statistics_service import (
    SessionStatisticsCapabilityError,
    UnknownSessionStatisticsInstrumentError,
)
from api.session_statistics import (
    SESSION_STATISTIC_SCHEMA_VERSION,
    SessionStatisticMetricCode,
)


class SessionStatisticsWriteService:
    def __init__(
        self,
        repository: SessionStatisticsRepository,
        routing_repository: InstrumentRoutingRepository,
    ) -> None:
        self._repository = repository
        self._routing_repository = routing_repository

    def store_snapshot(
        self,
        instrument_id: int,
        symbol: str,
        period_start: date,
        period_end: date,
        metrics: Mapping[SessionStatisticMetricCode, Decimal],
        *,
        source: str,
        fetched_at: datetime,
    ) -> int:
        if fetched_at.tzinfo is None:
            raise ValueError("fetched_at must be timezone-aware")
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
        if symbol.upper().strip() != route.provider_symbol:
            raise ValueError(
                f"Session statistics for {symbol} cannot update instrument "
                f"{instrument_id} ({route.provider_symbol})"
            )
        return self._repository.store_snapshot(SessionStatisticSnapshotWrite(
            instrument_id=instrument_id,
            period_start=period_start,
            period_end=period_end,
            source=source,
            schema_version=SESSION_STATISTIC_SCHEMA_VERSION,
            fetched_at=fetched_at,
            metrics=metrics,
        ))
