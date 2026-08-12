"""Company-list use cases independent from SQLAlchemy and FastAPI."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from api.repositories.company_repository import (
    CompanyQuery,
    CompanyRecord,
    CompanyListFacets,
    CompanyRepository,
    UniverseRecord,
)
ALL_UNIVERSES = {"US_ALL": "US", "VN_ALL": "VN"}
DEFAULT_PRICE_BASIS = {
    "US": "adjusted",
    "VN": "provider_unspecified",
}
UNIVERSE_ORDER = (
    "US_ALL", "US100", "US2000", "US500", "US30",
    "VN_ALL", "VNALL", "VN100", "VN30", "VNMID", "VNSML",
)


class UnknownUniverseError(ValueError):
    pass


@dataclass(frozen=True)
class CompanyList:
    id: str
    name: str
    country_code: str
    description: str
    as_of: str | None
    fetched_at: datetime | None
    total: int
    offset: int
    limit: int
    companies: tuple[CompanyRecord, ...]
    facets: CompanyListFacets


class CompanyService:
    def __init__(self, repository: CompanyRepository):
        self._repository = repository

    def list_universes(self) -> tuple[UniverseRecord, ...]:
        stored = {row.code: row for row in self._repository.list_universes()}
        combined = {
            code: self._combined_universe(code, market, tuple(stored.values()))
            for code, market in ALL_UNIVERSES.items()
        }
        return tuple(
            combined[code] if code in combined else stored[code]
            for code in UNIVERSE_ORDER
            if code in combined or code in stored
        )

    def list_companies(
        self,
        universe_id: str,
        *,
        search: str | None = None,
        sector: str | None = None,
        industry: str | None = None,
        venue_code: str | None = None,
        offset: int = 0,
        limit: int = 5000,
    ) -> CompanyList:
        universe_id = universe_id.upper()
        universes = {row.code: row for row in self._repository.list_universes()}
        if universe_id in ALL_UNIVERSES:
            country_code = ALL_UNIVERSES[universe_id]
            universe = self._combined_universe(
                universe_id, country_code, tuple(universes.values())
            )
            stored_universe = None
        else:
            universe = universes.get(universe_id)
            if universe is None:
                raise UnknownUniverseError(f"Unknown company universe: {universe_id}")
            country_code = universe.country_code
            stored_universe = universe_id

        companies, total, facets = self._repository.list_companies(CompanyQuery(
            country_code=country_code,
            price_basis=DEFAULT_PRICE_BASIS[country_code],
            universe=stored_universe,
            search=search,
            sector=sector,
            industry=industry,
            venue_code=venue_code,
            offset=offset,
            limit=limit,
        ))
        return CompanyList(
            id=universe.code,
            name=universe.name,
            country_code=country_code,
            description=universe.description,
            as_of=universe.as_of,
            fetched_at=universe.fetched_at,
            total=total,
            offset=offset,
            limit=limit,
            companies=companies,
            facets=facets,
        )

    def _combined_universe(
        self,
        code: str,
        country_code: str,
        universes: tuple[UniverseRecord, ...],
    ) -> UniverseRecord:
        country_universes = tuple(
            row for row in universes if row.country_code == country_code
        )
        count = self._repository.count_companies(CompanyQuery(
            country_code=country_code,
            price_basis=DEFAULT_PRICE_BASIS[country_code],
        ))
        fetched = [row.fetched_at for row in country_universes if row.fetched_at]
        as_of_values = [row.as_of for row in country_universes if row.as_of]
        return UniverseRecord(
            code=code,
            name=f"{country_code} Companies",
            country_code=country_code,
            description=f"All saved {country_code} companies merged without duplicate tickers.",
            as_of=" / ".join(as_of_values) or None,
            fetched_at=max(fetched) if fetched else None,
            company_count=count,
        )
