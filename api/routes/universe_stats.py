"""Universe Stats analysis endpoint."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from api.deps import get_universe_stats_service
from api.schemas.universe_stats import (
    UniverseStatsErrorResponse,
    UniverseInstrumentStatsResponse,
    UniverseStatsPointResponse,
    UniverseStatsRequest,
    UniverseStatsResponse,
    UniverseStatsResultResponse,
)
from api.services.universe_stats_service import (
    UNIVERSE_STATS_FORMULA_VERSION,
    UNIVERSE_STATS_HISTORY_YEARS,
    UNIVERSE_STATS_MINIMUM_COVERAGE,
    UNIVERSE_STATS_WINDOW,
    UniverseStatsService,
)


router = APIRouter(prefix="/universe-stats", tags=["universe-stats"])


@router.post(
    "/run",
    response_model=UniverseStatsResponse,
    operation_id="runUniverseStats",
)
def run_universe_stats(
    request: UniverseStatsRequest,
    service: Annotated[UniverseStatsService, Depends(get_universe_stats_service)],
) -> UniverseStatsResponse:
    run = service.run(request.universe_codes)
    return UniverseStatsResponse(
        formula_version=UNIVERSE_STATS_FORMULA_VERSION,
        window=UNIVERSE_STATS_WINDOW,
        minimum_coverage_pct=UNIVERSE_STATS_MINIMUM_COVERAGE * 100.0,
        history_years=UNIVERSE_STATS_HISTORY_YEARS,
        membership_mode="current_snapshot",
        results=[
            UniverseStatsResultResponse(
                universe_code=result.universe_code,
                universe_name=result.universe_name,
                member_count=result.member_count,
                instruments_with_history=result.instruments_with_history,
                missing_history_count=result.missing_history_count,
                first_date=result.first_date,
                last_date=result.last_date,
                sources=list(result.sources),
                fetched_at=result.fetched_at,
                points=[UniverseStatsPointResponse(**vars(point)) for point in result.points],
                instruments=[
                    UniverseInstrumentStatsResponse(**vars(instrument))
                    for instrument in result.instruments
                ],
            )
            for result in run.results
        ],
        errors=[UniverseStatsErrorResponse(**vars(error)) for error in run.errors],
    )
