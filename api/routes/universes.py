"""Canonical universe discovery endpoints."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import get_universe_service
from api.schemas.universe import (
    UniverseCatalogResponse,
    UniverseListResponse,
    UniverseSyncRunPageResponse,
    UniverseSyncRunResponse,
)
from api.services.universe_service import UnknownUniverseError, UniverseService


router = APIRouter(prefix="/universes", tags=["universes"])


@router.get("", response_model=UniverseListResponse, operation_id="listUniverses")
def list_universes(
    service: Annotated[UniverseService, Depends(get_universe_service)],
) -> UniverseListResponse:
    return UniverseListResponse(
        universes=[
            UniverseCatalogResponse(
                id=row.id,
                code=row.code,
                name=row.name,
                description=row.description,
                source=row.source,
                as_of=row.as_of,
                fetched_at=row.fetched_at,
                instrument_count=row.instrument_count,
                active_instrument_count=row.active_instrument_count,
                instrument_types=list(row.instrument_types),
                venue_codes=list(row.venue_codes),
            )
            for row in service.list_universes()
        ]
    )


@router.get(
    "/{universe_id}/sync-runs",
    response_model=UniverseSyncRunPageResponse,
    operation_id="listUniverseSyncRuns",
)
def list_universe_sync_runs(
    universe_id: int,
    service: Annotated[UniverseService, Depends(get_universe_service)],
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> UniverseSyncRunPageResponse:
    try:
        page = service.list_sync_runs(universe_id, offset=offset, limit=limit)
    except UnknownUniverseError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return UniverseSyncRunPageResponse(
        universe_id=page.universe_id,
        universe_code=page.universe_code,
        runs=[UniverseSyncRunResponse(**row.__dict__) for row in page.runs],
        total=page.total,
        offset=page.offset,
        limit=page.limit,
    )
