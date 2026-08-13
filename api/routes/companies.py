"""Database-backed company queries."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from api.deps import get_company_catalog_service
from api.schemas.company import (
    CompanyCatalogItemResponse,
    CompanyCatalogResponse,
    CompanyCatalogFacetsResponse,
    CompanyIdentifierResponse,
    CompanyInstrumentResponse,
    FacetCountResponse,
    CompanyCountryCode,
)
from api.services.company_catalog_service import CompanyCatalogService


router = APIRouter(prefix="/companies", tags=["companies"])


@router.get(
    "",
    response_model=CompanyCatalogResponse,
    operation_id="listCompanies",
)
def list_companies(
    service: Annotated[CompanyCatalogService, Depends(get_company_catalog_service)],
    country: CompanyCountryCode | None = Query(default=None),
    search: str | None = Query(default=None, max_length=100),
    sector: str | None = Query(default=None, max_length=255),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> CompanyCatalogResponse:
    companies, total, facets = service.list_companies(
        country=country,
        search=search,
        sector=sector,
        offset=offset,
        limit=limit,
    )
    return CompanyCatalogResponse(
        total=total,
        offset=offset,
        limit=limit,
        companies=[
            CompanyCatalogItemResponse(
                id=company.id,
                display_name=company.display_name,
                legal_name=company.legal_name,
                country_code=company.country_code,
                sector=company.sector,
                industry=company.industry,
                is_active=company.is_active,
                identifiers=[
                    CompanyIdentifierResponse(
                        namespace=identifier.namespace,
                        value=identifier.value,
                    )
                    for identifier in company.identifiers
                ],
                instruments=[
                    CompanyInstrumentResponse(
                        id=instrument.id,
                        ticker=instrument.ticker,
                        instrument_type=instrument.instrument_type,
                        share_class=instrument.share_class,
                        venue_code=instrument.venue_code,
                        currency=instrument.currency,
                        is_active=instrument.is_active,
                        universes=list(instrument.universes),
                    )
                    for instrument in company.instruments
                ],
            )
            for company in companies
        ],
        facets=CompanyCatalogFacetsResponse(
            countries=[
                FacetCountResponse(value=facet.value, count=facet.count)
                for facet in facets.countries
            ],
            sectors=[
                FacetCountResponse(value=facet.value, count=facet.count)
                for facet in facets.sectors
            ],
        ),
    )
