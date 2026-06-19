"""Event-analysis endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.deps import fetch_prices
from api.schemas.events import (
    NewLowCurrentEpisodeSchema,
    NewLowEpisodeSchema,
    NewLowEpisodesRequest,
    NewLowEpisodesResponse,
    NewLowForwardStatsSchema,
    NewLowSymbolResultSchema,
    NewLowTimeSeriesPointSchema,
)
from trading_engine.event_analysis import analyze_new_low_episodes
from trading_engine.types import InsufficientDataError

router = APIRouter(prefix="/events", tags=["events"])


@router.post("/new-low-episodes", response_model=NewLowEpisodesResponse)
def new_low_episodes_endpoint(req: NewLowEpisodesRequest) -> NewLowEpisodesResponse:
    symbols = [s.upper().strip() for s in req.symbols if s.strip()]
    if not symbols:
        raise HTTPException(status_code=422, detail="At least one symbol is required")

    prices = fetch_prices(symbols, req.date_range.start, req.date_range.end, req.data_source)
    results: list[NewLowSymbolResultSchema] = []

    for symbol in symbols:
        if symbol not in prices:
            continue
        try:
            result = analyze_new_low_episodes(
                prices=prices[symbol],
                lookback_sessions=req.lookback_sessions,
                quick_recovery_sessions=req.quick_recovery_sessions,
                forward_horizons=req.forward_horizons,
            )
        except (InsufficientDataError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=f"{symbol}: {exc}") from exc

        results.append(_to_new_low_schema(result))

    return NewLowEpisodesResponse(results=results)


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
