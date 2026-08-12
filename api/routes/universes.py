"""Canonical universe discovery endpoints."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from api.deps import get_universe_service
from api.schemas.universe import UniverseCatalogResponse, UniverseListResponse
from api.services.universe_service import UniverseService


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
