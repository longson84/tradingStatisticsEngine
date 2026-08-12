"""Read-only canonical venue catalog endpoints."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from api.deps import get_venue_service
from api.schemas.venue import VenueListResponse, VenueResponse
from api.services.venue_service import VenueService


router = APIRouter(prefix="/venues", tags=["venues"])


@router.get("", response_model=VenueListResponse, operation_id="listVenues")
def list_venues(
    service: Annotated[VenueService, Depends(get_venue_service)],
) -> VenueListResponse:
    rows = service.list_venues()
    return VenueListResponse(
        total=len(rows),
        venues=[VenueResponse.model_validate(row, from_attributes=True) for row in rows],
    )
