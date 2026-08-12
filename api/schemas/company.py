"""Public company API contracts generated into frontend TypeScript types."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


MarketCode = Literal["US", "VN"]
CompanyUniverseId = Literal[
    "US_ALL", "US100", "US2000", "US500", "US30",
    "VN_ALL", "VNALL", "VN100", "VN30", "VNMID", "VNSML",
]


class CompanyResponse(BaseModel):
    instrument_id: int
    ticker: str
    company_name: str
    country_code: MarketCode
    sector: str | None = None
    industry: str | None = None
    venue_code: str | None = None
    lists: list[str]
    first_session: date | None
    last_session: date | None
    stored_sessions: int


class CompanyUniverseResponse(BaseModel):
    id: CompanyUniverseId
    name: str
    country_code: MarketCode
    description: str
    company_count: int
    as_of: str | None = None
    fetched_at: datetime | None = None


class CompanyUniversesResponse(BaseModel):
    universes: list[CompanyUniverseResponse]


class FacetCountResponse(BaseModel):
    value: str
    count: int


class CompanyListFacetsResponse(BaseModel):
    all_count: int
    sectors: list[FacetCountResponse]
    universes: list[FacetCountResponse]


class CompanyListResponse(BaseModel):
    id: CompanyUniverseId
    name: str
    country_code: MarketCode
    description: str
    as_of: str | None = None
    fetched_at: datetime | None = None
    total: int
    offset: int
    limit: int
    companies: list[CompanyResponse]
    facets: CompanyListFacetsResponse


class CompanyIdentifierResponse(BaseModel):
    namespace: str
    value: str


class CompanyInstrumentResponse(BaseModel):
    id: int
    ticker: str
    instrument_type: str
    share_class: str | None = None
    venue_code: str | None = None
    currency: str
    is_active: bool
    universes: list[str]


class CompanyCatalogItemResponse(BaseModel):
    id: int
    display_name: str
    legal_name: str | None = None
    country_code: MarketCode
    sector: str | None = None
    industry: str | None = None
    is_active: bool
    identifiers: list[CompanyIdentifierResponse]
    instruments: list[CompanyInstrumentResponse]


class CompanyCatalogFacetsResponse(BaseModel):
    countries: list[FacetCountResponse]
    sectors: list[FacetCountResponse]


class CompanyCatalogResponse(BaseModel):
    total: int
    offset: int
    limit: int
    companies: list[CompanyCatalogItemResponse]
    facets: CompanyCatalogFacetsResponse
