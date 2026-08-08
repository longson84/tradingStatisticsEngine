"""Persistence-agnostic company repository contract."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol


@dataclass(frozen=True)
class CompanyRecord:
    ticker: str
    company_name: str
    market: str
    sector: str | None
    industry: str | None
    exchange: str | None
    lists: tuple[str, ...]
    first_session: date | None
    last_session: date | None
    stored_sessions: int


@dataclass(frozen=True)
class UniverseRecord:
    code: str
    name: str
    market: str
    description: str
    as_of: str | None
    fetched_at: datetime | None
    company_count: int


@dataclass(frozen=True)
class CompanyQuery:
    market: str
    price_basis: str
    universe: str | None = None
    search: str | None = None
    sector: str | None = None
    industry: str | None = None
    exchange: str | None = None
    offset: int = 0
    limit: int = 5000


class CompanyRepository(Protocol):
    def list_universes(self) -> tuple[UniverseRecord, ...]: ...

    def list_companies(
        self,
        query: CompanyQuery,
    ) -> tuple[tuple[CompanyRecord, ...], int]: ...
