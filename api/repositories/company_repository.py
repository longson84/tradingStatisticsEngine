"""Persistence-agnostic company repository contract."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol


@dataclass(frozen=True)
class CompanyRecord:
    instrument_id: int
    ticker: str
    company_name: str
    country_code: str
    sector: str | None
    industry: str | None
    venue_code: str | None
    lists: tuple[str, ...]
    first_session: date | None
    last_session: date | None
    stored_sessions: int


@dataclass(frozen=True)
class UniverseRecord:
    code: str
    name: str
    country_code: str
    description: str
    as_of: str | None
    fetched_at: datetime | None
    company_count: int


@dataclass(frozen=True)
class CompanyQuery:
    country_code: str
    price_basis: str
    universe: str | None = None
    search: str | None = None
    sector: str | None = None
    industry: str | None = None
    venue_code: str | None = None
    offset: int = 0
    limit: int = 5000


@dataclass(frozen=True)
class FacetCount:
    value: str
    count: int


@dataclass(frozen=True)
class CompanyListFacets:
    all_count: int
    sectors: tuple[FacetCount, ...]
    universes: tuple[FacetCount, ...]


class CompanyRepository(Protocol):
    def list_universes(self) -> tuple[UniverseRecord, ...]: ...

    def count_companies(self, query: CompanyQuery) -> int: ...

    def list_companies(
        self,
        query: CompanyQuery,
    ) -> tuple[tuple[CompanyRecord, ...], int, CompanyListFacets]: ...
