"""Database-only exact-period Instrument session statistics endpoint."""
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import get_session_statistics_service
from api.schemas.session_statistics import (
    InstrumentSessionStatisticsResponse,
    SessionStatisticMetricResponse,
)
from api.services.session_statistics_service import (
    SessionStatisticsCapabilityError,
    SessionStatisticsService,
    SessionStatisticsUnavailableError,
    UnknownSessionStatisticsInstrumentError,
)


router = APIRouter(prefix="/instruments", tags=["instruments"])


@router.get(
    "/{instrument_id}/session-statistics",
    response_model=InstrumentSessionStatisticsResponse,
    operation_id="getInstrumentSessionStatistics",
)
def get_instrument_session_statistics(
    instrument_id: int,
    service: Annotated[SessionStatisticsService, Depends(get_session_statistics_service)],
    start: date = Query(...),
    end: date = Query(...),
) -> InstrumentSessionStatisticsResponse:
    try:
        result = service.get_stored_snapshot(instrument_id, start, end)
    except UnknownSessionStatisticsInstrumentError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (
        SessionStatisticsCapabilityError,
        SessionStatisticsUnavailableError,
        ValueError,
    ) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    snapshot = result.snapshot
    instrument = result.instrument
    return InstrumentSessionStatisticsResponse(
        snapshot_id=snapshot.snapshot_id,
        instrument_id=instrument.instrument_id,
        symbol=instrument.symbol,
        instrument_type=instrument.instrument_type,
        venue_code=instrument.venue_code,
        currency=instrument.currency,
        period_start=snapshot.period_start,
        period_end=snapshot.period_end,
        source=snapshot.source,
        schema_version=snapshot.schema_version,
        fetched_at=snapshot.fetched_at,
        metrics=[SessionStatisticMetricResponse(
            code=item.definition.code,
            group=item.definition.group,
            label=item.definition.label,
            unit=item.definition.unit,
            order=item.definition.order,
            value=float(item.value),
        ) for item in result.metrics],
    )
