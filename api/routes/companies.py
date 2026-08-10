"""Database-backed company queries."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import get_company_catalog_service, get_company_service
from api.schemas.company import (
    CompanyListResponse,
    CompanyCatalogItemResponse,
    CompanyCatalogResponse,
    CompanyCatalogFacetsResponse,
    CompanyIdentifierResponse,
    CompanyInstrumentResponse,
    CompanyListFacetsResponse,
    FacetCountResponse,
    CompanyResponse,
    CompanyUniverseId,
    CompanyUniverseResponse,
    CompanyUniversesResponse,
    MarketCode,
)
from api.services.company_service import CompanyService, UnknownUniverseError
from api.services.company_catalog_service import CompanyCatalogService


router = APIRouter(prefix="/companies", tags=["companies"])


@router.get(
    "/catalog",
    response_model=CompanyCatalogResponse,
    operation_id="listCompanyCatalog",
)
def list_company_catalog(
    service: Annotated[CompanyCatalogService, Depends(get_company_catalog_service)],
    country: MarketCode | None = Query(default=None),
    search: str | None = Query(default=None, max_length=100),
    sector: str | None = Query(default=None, max_length=255),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=5000, ge=1, le=5000),
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
                        market=instrument.market,
                        instrument_type=instrument.instrument_type,
                        share_class=instrument.share_class,
                        exchange=instrument.exchange,
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


@router.get(
    "/universes",
    response_model=CompanyUniversesResponse,
    operation_id="listCompanyUniverses",
)
def list_company_universes(
    service: Annotated[CompanyService, Depends(get_company_service)],
) -> CompanyUniversesResponse:
    return CompanyUniversesResponse(
        universes=[
            CompanyUniverseResponse(
                id=row.code,
                name=row.name,
                market=row.market,
                description=row.description,
                company_count=row.company_count,
                as_of=row.as_of,
                fetched_at=row.fetched_at,
            )
            for row in service.list_universes()
        ]
    )


@router.get(
    "",
    response_model=CompanyListResponse,
    operation_id="listCompanies",
)
def list_companies(
    service: Annotated[CompanyService, Depends(get_company_service)],
    universe: CompanyUniverseId = Query(default="US_ALL"),
    search: str | None = Query(default=None, max_length=100),
    sector: str | None = Query(default=None, max_length=255),
    industry: str | None = Query(default=None, max_length=255),
    exchange: str | None = Query(default=None, max_length=32),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=5000, ge=1, le=5000),
) -> CompanyListResponse:
    try:
        result = service.list_companies(
            universe,
            search=search,
            sector=sector,
            industry=industry,
            exchange=exchange,
            offset=offset,
            limit=limit,
        )
    except UnknownUniverseError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return CompanyListResponse(
        id=result.id,
        name=result.name,
        market=result.market,
        description=result.description,
        as_of=result.as_of,
        fetched_at=result.fetched_at,
        total=result.total,
        offset=result.offset,
        limit=result.limit,
        companies=[
            CompanyResponse(
                ticker=row.ticker,
                company_name=row.company_name,
                market=row.market,
                sector=row.sector,
                industry=row.industry,
                exchange=row.exchange,
                lists=list(row.lists),
                first_session=row.first_session,
                last_session=row.last_session,
                stored_sessions=row.stored_sessions,
            )
            for row in result.companies
        ],
        facets=CompanyListFacetsResponse(
            all_count=result.facets.all_count,
            sectors=[
                FacetCountResponse(value=facet.value, count=facet.count)
                for facet in result.facets.sectors
            ],
            universes=[
                FacetCountResponse(value=facet.value, count=facet.count)
                for facet in result.facets.universes
            ],
        ),
    )
