"""Public database-backed Instrument participant-flow endpoint."""
from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import get_instrument_flow_service
from api.schemas.market_flow import InstrumentFlowPointResponse, InstrumentFlowResponse
from api.services.instrument_flow_service import (
    InstrumentFlowCapabilityError,
    InstrumentFlowService,
    InstrumentFlowUnavailableError,
    UnknownFlowInstrumentError,
)


router = APIRouter(prefix="/instruments", tags=["instruments"])


@router.get(
    "/{instrument_id}/market-flows",
    response_model=InstrumentFlowResponse,
    operation_id="getInstrumentMarketFlows",
)
def get_instrument_market_flows(
    instrument_id: int,
    service: Annotated[InstrumentFlowService, Depends(get_instrument_flow_service)],
    participant_type: Annotated[
        Literal["foreign"], Query(json_schema_extra={"enum": ["foreign"]})
    ] = "foreign",
    start: date | None = None,
    end: date | None = None,
) -> InstrumentFlowResponse:
    try:
        result = service.get_stored_flow(
            instrument_id, participant_type, start=start, end=end
        )
    except UnknownFlowInstrumentError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (InstrumentFlowCapabilityError, InstrumentFlowUnavailableError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return InstrumentFlowResponse(
        instrument_id=result.instrument.instrument_id,
        symbol=result.instrument.symbol,
        instrument_type=result.instrument.instrument_type,
        venue_code=result.instrument.venue_code,
        currency=result.instrument.currency,
        participant_type=result.participant_type,
        first_date=result.coverage.first_date,
        last_date=result.coverage.last_date,
        expected_last_session=result.expected_last_session,
        is_stale=result.is_stale,
        row_count=result.coverage.row_count,
        source=result.coverage.source,
        fetched_at=result.coverage.fetched_at,
        observations=[InstrumentFlowPointResponse(
            date=row.trading_date,
            buy_volume=float(row.buy_volume),
            buy_value=float(row.buy_value),
            sell_volume=float(row.sell_volume),
            sell_value=float(row.sell_value),
            net_volume=float(row.net_volume),
            net_value=float(row.net_value),
        ) for row in result.observations],
    )
