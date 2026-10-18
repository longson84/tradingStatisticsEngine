"""Read stored participant-flow history by exact Instrument identity."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime

from api.instrument_data_routing import (
    UnsupportedInstrumentRouteError,
    resolve_instrument_data_route,
)
from api.market_sessions import latest_completed_venue_session
from api.repositories.instrument_flow_repository import (
    FlowInstrumentRecord,
    InstrumentFlowCoverageRecord,
    InstrumentFlowQuery,
    InstrumentFlowRecord,
    InstrumentFlowRepository,
    ParticipantType,
)
from api.repositories.instrument_routing_repository import InstrumentRoutingRepository


class UnknownFlowInstrumentError(ValueError):
    """The requested canonical Instrument does not exist."""


class InstrumentFlowCapabilityError(ValueError):
    """The requested Instrument does not support this flow dataset."""


class InstrumentFlowUnavailableError(ValueError):
    """No stored observations exist for a supported Instrument."""


@dataclass(frozen=True)
class InstrumentFlowData:
    instrument: FlowInstrumentRecord
    participant_type: ParticipantType
    coverage: InstrumentFlowCoverageRecord
    observations: tuple[InstrumentFlowRecord, ...]
    expected_last_session: date
    is_stale: bool


class InstrumentFlowService:
    def __init__(
        self,
        repository: InstrumentFlowRepository,
        routing_repository: InstrumentRoutingRepository,
    ) -> None:
        self._repository = repository
        self._routing_repository = routing_repository

    def get_stored_flow(
        self,
        instrument_id: int,
        participant_type: ParticipantType,
        *,
        start: date | None = None,
        end: date | None = None,
        now: datetime | None = None,
    ) -> InstrumentFlowData:
        if start is not None and end is not None and start > end:
            raise ValueError("start date must be on or before end date")
        instrument = self._repository.get_instrument(instrument_id)
        metadata = self._routing_repository.get_instrument_route_metadata(instrument_id)
        if instrument is None or metadata is None:
            raise UnknownFlowInstrumentError(f"Unknown instrument: {instrument_id}")
        try:
            route = resolve_instrument_data_route(metadata)
        except UnsupportedInstrumentRouteError as exc:
            raise InstrumentFlowCapabilityError(
                f"Instrument {instrument_id} does not support foreign_flow"
            ) from exc
        if participant_type != "foreign" or "foreign_flow" not in route.capabilities:
            raise InstrumentFlowCapabilityError(
                f"Instrument {instrument_id} does not support foreign_flow"
            )
        coverage = self._repository.get_coverage(instrument_id, participant_type)
        if coverage is None:
            raise InstrumentFlowUnavailableError(
                f"No stored {participant_type} flow for instrument {instrument_id}"
            )
        observations = tuple(self._repository.iter_observations(InstrumentFlowQuery(
            instrument_id=instrument_id,
            participant_type=participant_type,
            start=start,
            end=end,
        )))
        expected = latest_completed_venue_session(
            now or datetime.now(UTC), route.schedule
        )
        return InstrumentFlowData(
            instrument=instrument,
            participant_type=participant_type,
            coverage=coverage,
            observations=observations,
            expected_last_session=expected,
            is_stale=coverage.last_date < expected,
        )
