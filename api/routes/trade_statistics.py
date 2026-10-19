"""Database-only requested-range Instrument daily trading activity endpoint."""
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import (
    get_trade_statistics_service,
    get_trading_activity_scanner_service,
)
from api.schemas.trade_statistics import (
    DailyTradeStatisticResponse,
    InstrumentTradeStatisticsResponse,
    TurnoverIntensityAnalysisResponse,
    TurnoverIntensityPointResponse,
    TradingActivityScannerCountsResponse,
    TradingActivityScannerItemResponse,
    TradingActivityScannerResponse,
)
from api.services.trade_statistics_service import (
    TradeStatisticsCapabilityError,
    TradeStatisticsService,
    TradeStatisticsUnavailableError,
    TradingActivityScannerService,
    UnknownTradeStatisticsInstrumentError,
    UnknownTradingActivityScopeError,
)
from api.trade_statistics import TRADE_STATISTIC_STORAGE_COLUMNS


router = APIRouter(prefix="/instruments", tags=["instruments"])
scanner_router = APIRouter(prefix="/trading-activity", tags=["trading activity"])


def _json_number(value: Decimal) -> int | float:
    """Keep whole values exact on the wire; fractions follow the API float convention.

    JavaScript consumers still use IEEE-754 numbers; this is not a lossless
    decimal client contract. Database and service values remain Decimal.
    """
    return int(value) if value == value.to_integral_value() else float(value)


@scanner_router.get(
    "/scanner",
    response_model=TradingActivityScannerResponse,
    operation_id="scanTradingActivity",
)
def scan_trading_activity(
    service: Annotated[
        TradingActivityScannerService,
        Depends(get_trading_activity_scanner_service),
    ],
    scope_type: Literal["universe", "watchlist"] = Query(...),
    scope_id: str = Query(..., min_length=1),
) -> TradingActivityScannerResponse:
    try:
        result = service.scan(scope_type, scope_id)
    except UnknownTradingActivityScopeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return TradingActivityScannerResponse(
        scope_type=result.scope_type,
        scope_id=result.scope_id,
        scope_name=result.scope_name,
        target_session=result.target_session,
        formula_version=result.formula_version,
        baseline_sessions=result.baseline_sessions,
        counts=TradingActivityScannerCountsResponse(**result.counts),
        items=[TradingActivityScannerItemResponse(
            instrument_id=item.instrument_id,
            symbol=item.symbol,
            display_name=item.display_name,
            venue_code=item.venue_code,
            status=item.status,
            rank=item.rank,
            latest_session=item.latest_session,
            turnover_intensity=item.turnover_intensity,
            baseline=item.baseline,
            anomaly_score=item.anomaly_score,
            unavailable_reason=item.unavailable_reason,
        ) for item in result.items],
    )


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
        turnover_intensity=TurnoverIntensityAnalysisResponse(
            formula_version=result.turnover_intensity.formula_version,
            baseline_sessions=result.turnover_intensity.baseline_sessions,
            points=[TurnoverIntensityPointResponse(
                trading_date=point.session,
                intensity=point.intensity,
                baseline=point.baseline,
                anomaly_score=point.anomaly_score,
                unavailable_reason=point.unavailable_reason,
            ) for point in result.turnover_intensity.points],
        ),
    )
