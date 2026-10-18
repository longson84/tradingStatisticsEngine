"""Database-only requested-range Instrument daily trading activity endpoint."""
from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import get_trade_statistics_service
from api.schemas.trade_statistics import (
    DailyTradeStatisticResponse,
    InstrumentTradeStatisticsResponse,
)
from api.services.trade_statistics_service import (
    TradeStatisticsCapabilityError,
    TradeStatisticsService,
    TradeStatisticsUnavailableError,
    UnknownTradeStatisticsInstrumentError,
)
from api.trade_statistics import TRADE_STATISTIC_STORAGE_COLUMNS


router = APIRouter(prefix="/instruments", tags=["instruments"])


def _json_number(value: Decimal) -> int | float:
    """Keep whole values exact on the wire; fractions follow the API float convention.

    JavaScript consumers still use IEEE-754 numbers; this is not a lossless
    decimal client contract. Database and service values remain Decimal.
    """
    return int(value) if value == value.to_integral_value() else float(value)


@router.get(
    "/{instrument_id}/trade-statistics",
    response_model=InstrumentTradeStatisticsResponse,
    operation_id="getInstrumentTradeStatistics",
)
def get_instrument_trade_statistics(
    instrument_id: int,
    service: Annotated[TradeStatisticsService, Depends(get_trade_statistics_service)],
    start: date = Query(...),
    end: date = Query(...),
) -> InstrumentTradeStatisticsResponse:
    try:
        result = service.get_stored_range(instrument_id, start, end)
    except UnknownTradeStatisticsInstrumentError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (
        TradeStatisticsCapabilityError,
        TradeStatisticsUnavailableError,
        ValueError,
    ) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    instrument = result.instrument
    return InstrumentTradeStatisticsResponse(
        instrument_id=instrument.instrument_id,
        symbol=instrument.symbol,
        instrument_type=instrument.instrument_type,
        venue_code=instrument.venue_code,
        currency=instrument.currency,
        requested_start=result.requested_start,
        requested_end=result.requested_end,
        first_date=result.first_date,
        last_date=result.last_date,
        row_count=len(result.rows),
        rows=[DailyTradeStatisticResponse(
            trading_date=row.trading_date,
            source=row.source,
            schema_version=row.schema_version,
            fetched_at=row.fetched_at,
            **{name: _json_number(getattr(row, name)) for name in TRADE_STATISTIC_STORAGE_COLUMNS},
        ) for row in result.rows],
    )
