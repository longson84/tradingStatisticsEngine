"""Read-only canonical reference-rate catalog endpoints."""
from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from api.deps import get_reference_rate_service
from api.repositories.reference_rate_repository import (
    REFERENCE_RATE_PRICE_BASIS,
)
from api.schemas.reference_rates import (
    ReferenceRateFacetCountResponse,
    ReferenceRateFacetsResponse,
    ReferenceRateInstrumentResponse,
    ReferenceRateListResponse,
    ReferenceRateSummaryResponse,
)
from api.services.reference_rate_service import ReferenceRateService


router = APIRouter(prefix="/reference-rates", tags=["reference-rates"])


@router.get(
    "",
    response_model=ReferenceRateListResponse,
    operation_id="listReferenceRates",
)
def list_reference_rates(
    service: Annotated[
        ReferenceRateService,
        Depends(get_reference_rate_service),
    ],
    search: str | None = Query(default=None, max_length=100),
    base_asset: str | None = Query(default=None, max_length=64),
    quote_asset: str | None = Query(default=None, max_length=64),
    status: Literal["active", "inactive", "all"] = Query(default="active"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
) -> ReferenceRateListResponse:
    result = service.list_reference_rates(
        search=search,
        base_asset=base_asset,
        quote_asset=quote_asset,
        is_active={"active": True, "inactive": False, "all": None}[status],
        offset=offset,
        limit=limit,
    )
    return ReferenceRateListResponse(
        total=result.total,
        offset=offset,
        limit=limit,
        instruments=[
            ReferenceRateInstrumentResponse(
                id=row.id,
                symbol=row.symbol,
                base_asset=row.base_asset,
                base_asset_name=row.base_asset_name,
                quote_asset=row.quote_asset,
                quote_asset_name=row.quote_asset_name,
                is_active=row.is_active,
                catalog_source=row.catalog_source,
                first_session=row.first_date,
                last_session=row.last_date,
                stored_sessions=row.stored_sessions,
                price_basis=REFERENCE_RATE_PRICE_BASIS,
                price_source=row.price_source,
                price_fetched_at=row.price_fetched_at,
            )
            for row in result.rows
        ],
        facets=ReferenceRateFacetsResponse(
            base_assets=[
                ReferenceRateFacetCountResponse(value=row.value, count=row.count)
                for row in result.facets.base_assets
            ],
            quote_assets=[
                ReferenceRateFacetCountResponse(value=row.value, count=row.count)
                for row in result.facets.quote_assets
            ],
            active_count=result.facets.active_count,
            inactive_count=result.facets.inactive_count,
        ),
        summary=ReferenceRateSummaryResponse(
            instrument_count=result.summary.instrument_count,
            active_count=result.summary.active_count,
            inactive_count=result.summary.inactive_count,
            with_history_count=result.summary.with_history_count,
            earliest_session=result.summary.earliest_session,
            latest_session=result.summary.latest_session,
        ),
    )
