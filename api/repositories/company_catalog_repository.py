"""Persistence-neutral company catalog contract."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class CompanyCatalogQuery:
    country: str | None = None
    search: str | None = None
    sector: str | None = None
    offset: int = 0
    limit: int = 5000


@dataclass(frozen=True)
class CompanyIdentifierRecord:
    namespace: str
    value: str


@dataclass(frozen=True)
class CompanyInstrumentRecord:
    id: int
    ticker: str
    instrument_type: str
    share_class: str | None
    venue_code: str | None
    currency: str
    is_active: bool
    universes: tuple[str, ...]


@dataclass(frozen=True)
class CompanyCatalogRecord:
    id: int
    display_name: str
    legal_name: str | None
    country_code: str
    sector: str | None
    industry: str | None
    is_active: bool
    identifiers: tuple[CompanyIdentifierRecord, ...]
    instruments: tuple[CompanyInstrumentRecord, ...]


@dataclass(frozen=True)
class CompanyCatalogFacetCount:
    value: str
    count: int


@dataclass(frozen=True)
class CompanyCatalogFacets:
    countries: tuple[CompanyCatalogFacetCount, ...]
    sectors: tuple[CompanyCatalogFacetCount, ...]


class CompanyCatalogRepository(Protocol):
    def list_companies(
        self,
        query: CompanyCatalogQuery,
    ) -> tuple[tuple[CompanyCatalogRecord, ...], int, CompanyCatalogFacets]: ...
