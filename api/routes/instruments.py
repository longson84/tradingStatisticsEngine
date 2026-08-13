"""Canonical instrument discovery endpoints."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from api.deps import get_instrument_analysis_service
from api.schemas.instrument import (
    InstrumentCatalogResponse,
    InstrumentCatalogItemResponse,
    InstrumentCatalogFacetsResponse,
    InstrumentFacetCountResponse,
    InstrumentScope,
)
from api.services.instrument_analysis_service import InstrumentAnalysisService


router = APIRouter(prefix="/instruments", tags=["instruments"])


@router.get(
    "",
    response_model=InstrumentCatalogResponse,
    operation_id="listInstruments",
)
def list_instruments(
    service: Annotated[
        InstrumentAnalysisService,
        Depends(get_instrument_analysis_service),
    ],
    scope: InstrumentScope | None = Query(default=None),
    universe: str | None = Query(default=None, max_length=64),
    search: str | None = Query(default=None, max_length=100),
    sector: str | None = Query(default=None, max_length=255),
    industry: str | None = Query(default=None, max_length=255),
    venue: str | None = Query(default=None, max_length=64),
    has_price_history: bool = Query(default=True),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> InstrumentCatalogResponse:
    result = service.list_instruments(
        scope=scope,
        universe=universe,
        search=search,
        sector=sector,
        industry=industry,
        venue_code=venue,
        has_price_history=has_price_history,
        offset=offset,
        limit=limit,
    )
    return InstrumentCatalogResponse(
        total=result.total,
        offset=offset,
        limit=limit,
        instruments=[
            InstrumentCatalogItemResponse(
                id=row.id,
                symbol=row.symbol,
                instrument_type=row.instrument_type,
                company_id=row.company_id,
                company_name=row.company_name,
                sector=row.sector,
                industry=row.industry,
                venue_code=row.venue_code,
                venue_name=row.venue_name,
                base_asset=row.base_asset,
                quote_asset=row.quote_asset,
                currency=row.currency,
                price_basis=row.price_basis,
                price_source=row.price_source,
                first_session=row.first_date,
                last_session=row.last_date,
                stored_sessions=row.stored_sessions,
                universes=list(row.universes),
            )
            for row in result.rows
        ],
        facets=InstrumentCatalogFacetsResponse(
            all_count=result.facets.all_count,
            sectors=[
                InstrumentFacetCountResponse(value=row.value, count=row.count)
                for row in result.facets.sectors
            ],
        ),
    )
