"""Public company API contracts generated into frontend TypeScript types."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


CompanyCountryCode = Literal["US", "VN"]
class FacetCountResponse(BaseModel):
    value: str
    count: int


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
    country_code: CompanyCountryCode
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
