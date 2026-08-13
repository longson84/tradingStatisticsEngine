"""Event-analysis endpoints."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_new_low_analysis_service
from api.schemas.events import (
    NewLowCurrentEpisodeSchema,
    NewLowEpisodeSchema,
    NewLowDeepRequest,
    NewLowDeepResponse,
    NewLowForwardStatsSchema,
    NewLowInstrumentIdentitySchema,
    NewLowPriceHistoryStatusSchema,
    NewLowSymbolResultSchema,
    NewLowTimeSeriesPointSchema,
)
from api.services.instrument_analysis_service import (
    InstrumentPriceUnavailableError,
    UnknownInstrumentError,
)
from api.services.new_low_analysis_service import (
    NEW_LOW_DEEP_FORMULA_VERSION,
    NewLowAnalysisService,
)
from trading_engine.types import InsufficientDataError

router = APIRouter(prefix="/events", tags=["events"])


@router.post(
    "/new-low-deep",
    response_model=NewLowDeepResponse,
    operation_id="analyzeNewLowDeep",
)
def new_low_deep_endpoint(
    req: NewLowDeepRequest,
    service: Annotated[
        NewLowAnalysisService, Depends(get_new_low_analysis_service)
    ],
) -> NewLowDeepResponse:
    try:
        result = service.analyze_deep(
            req.instrument_id,
            lookback_sessions=req.lookback_sessions,
            quick_recovery_sessions=req.quick_recovery_sessions,
            forward_horizons=req.forward_horizons,
        )
    except UnknownInstrumentError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (InstrumentPriceUnavailableError, InsufficientDataError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    instrument = result.instrument
    status = result.price_history
    return NewLowDeepResponse(
        formula_version=NEW_LOW_DEEP_FORMULA_VERSION,
        instrument=NewLowInstrumentIdentitySchema(
            id=instrument.id,
            symbol=instrument.symbol,
            instrument_type=instrument.instrument_type,
            company_name=instrument.company_name,
            venue_code=instrument.venue_code,
            venue_name=instrument.venue_name,
            base_asset=instrument.base_asset,
            quote_asset=instrument.quote_asset,
            currency=instrument.currency,
        ),
        price_history=NewLowPriceHistoryStatusSchema(
            source=status.source,
            price_basis=status.price_basis,
            first_session=status.first_session,
            data_last_session=status.data_last_session,
            expected_last_session=status.expected_last_session,
            stored_sessions=status.stored_sessions,
            is_stale=status.is_stale,
        ),
        analysis=_to_new_low_schema(result.analysis),
    )


def _to_new_low_schema(result) -> NewLowSymbolResultSchema:
    current = None
    if result.current is not None:
        c = result.current
        current = NewLowCurrentEpisodeSchema(
            start_date=c.start_date,
            start_price=c.start_price,
            recovery_level=c.recovery_level,
            current_date=c.current_date,
            current_price=c.current_price,
            current_down_pct=c.current_down_pct,
            current_return_pct=c.current_return_pct,
            max_down_pct=c.max_down_pct,
            sessions_elapsed=c.sessions_elapsed,
            ignored_new_lows=c.ignored_new_lows,
            low_date=c.low_date,
            low_price=c.low_price,
            days_to_low=c.days_to_low,
            recovery_needed_pct=c.recovery_needed_pct,
            max_down_percentile=c.max_down_percentile,
            ignored_lows_percentile=c.ignored_lows_percentile,
            duration_percentile=c.duration_percentile,
        )

    return NewLowSymbolResultSchema(
        symbol=result.symbol,
        first_date=result.first_date,
        last_date=result.last_date,
        total_bars=result.total_bars,
        latest_price=result.latest_price,
        lookback_sessions=result.lookback_sessions,
        quick_recovery_sessions=result.quick_recovery_sessions,
        raw_new_low_bars=result.raw_new_low_bars,
        kept_episodes=result.kept_episodes,
        completed_episodes=result.completed_episodes,
        active_episodes=result.active_episodes,
        quick_ignored_episodes=result.quick_ignored_episodes,
        total_ignored_new_lows=result.total_ignored_new_lows,
        max_down_percentiles={str(k): v for k, v in result.max_down_percentiles.items()},
        recovery_session_percentiles={str(k): v for k, v in result.recovery_session_percentiles.items()},
        ignored_new_low_percentiles={str(k): v for k, v in result.ignored_new_low_percentiles.items()},
        current=current,
        forward_stats=[
            NewLowForwardStatsSchema(
                horizon=s.horizon,
                count=s.count,
                return_percentiles={str(k): v for k, v in s.return_percentiles.items()},
                max_down_percentiles={str(k): v for k, v in s.max_down_percentiles.items()},
            )
            for s in result.forward_stats
        ],
        episodes=[
            NewLowEpisodeSchema(
                start_date=e.start_date,
                start_price=e.start_price,
                recovery_level=e.recovery_level,
                recovered=e.recovered,
                recovery_date=e.recovery_date,
                recovery_sessions=e.recovery_sessions,
                ignored_new_lows=e.ignored_new_lows,
                low_date=e.low_date,
                low_price=e.low_price,
                days_to_low=e.days_to_low,
                max_down_pct=e.max_down_pct,
                forward_returns={str(k): v for k, v in e.forward_returns.items()},
                forward_max_down={str(k): v for k, v in e.forward_max_down.items()},
            )
            for e in result.episodes
        ],
        time_series=[
            NewLowTimeSeriesPointSchema(
                date=row.date,
                close=float(row.close),
                is_new_low=bool(row.is_new_low),
            )
            for row in result.time_series.itertuples(index=False)
        ],
    )
