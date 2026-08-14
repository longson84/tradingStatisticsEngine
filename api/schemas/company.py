"""Public company API contracts generated into frontend TypeScript types."""
from __future__ import annotations

from pydantic import BaseModel


class FacetCountResponse(BaseModel):
    value: str
    count: int


class CompanyIdentifierResponse(BaseModel):
    namespace: str
    value: str


class CompanyInstrumentResponse(BaseModel):
    id: int
    symbol: str
    instrument_type: str
    share_class: str | None = None
    venue_code: str | None = None
    venue_country_code: str | None = None
    currency: str
    is_active: bool
    universes: list[str]


class CompanyCatalogItemResponse(BaseModel):
    id: int
    display_name: str
    legal_name: str | None = None
    domicile_country_code: str | None = None
    listing_country_codes: list[str]
    sector: str | None = None
    industry: str | None = None
    is_active: bool
    identifiers: list[CompanyIdentifierResponse]
    instruments: list[CompanyInstrumentResponse]


class CompanyCatalogFacetsResponse(BaseModel):
    listing_countries: list[FacetCountResponse]
    sectors: list[FacetCountResponse]


class CompanyCatalogResponse(BaseModel):
    total: int
    offset: int
    limit: int
    companies: list[CompanyCatalogItemResponse]
    facets: CompanyCatalogFacetsResponse
