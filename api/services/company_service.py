"""Company-list use cases independent from SQLAlchemy and FastAPI."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from api.repositories.company_repository import (
    CompanyQuery,
    CompanyRecord,
    CompanyRepository,
    UniverseRecord,
)


ALL_UNIVERSES = {"US_ALL": "US", "VN_ALL": "VN"}
UNIVERSE_ORDER = (
    "US_ALL", "US100", "US2000", "US500", "US30",
    "VN_ALL", "VN30", "VN100",
)


class UnknownUniverseError(ValueError):
    pass


@dataclass(frozen=True)
class CompanyList:
    id: str
    name: str
    market: str
    description: str
    as_of: str | None
    fetched_at: datetime | None
    total: int
    offset: int
    limit: int
    companies: tuple[CompanyRecord, ...]


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
        exchange: str | None = None,
        offset: int = 0,
        limit: int = 5000,
    ) -> CompanyList:
        universe_id = universe_id.upper()
        universes = {row.code: row for row in self._repository.list_universes()}
        if universe_id in ALL_UNIVERSES:
            market = ALL_UNIVERSES[universe_id]
            universe = self._combined_universe(
                universe_id, market, tuple(universes.values())
            )
            stored_universe = None
        else:
            universe = universes.get(universe_id)
            if universe is None:
                raise UnknownUniverseError(f"Unknown company universe: {universe_id}")
            market = universe.market
            stored_universe = universe_id

        companies, total = self._repository.list_companies(CompanyQuery(
            market=market,
            universe=stored_universe,
            search=search,
            sector=sector,
            industry=industry,
            exchange=exchange,
            offset=offset,
            limit=limit,
        ))
        return CompanyList(
            id=universe.code,
            name=universe.name,
            market=market,
            description=universe.description,
            as_of=universe.as_of,
            fetched_at=universe.fetched_at,
            total=total,
            offset=offset,
            limit=limit,
            companies=companies,
        )

    def _combined_universe(
        self,
        code: str,
        market: str,
        universes: tuple[UniverseRecord, ...],
    ) -> UniverseRecord:
        market_universes = tuple(row for row in universes if row.market == market)
        _, count = self._repository.list_companies(CompanyQuery(market=market, limit=1))
        fetched = [row.fetched_at for row in market_universes if row.fetched_at]
        as_of_values = [row.as_of for row in market_universes if row.as_of]
        return UniverseRecord(
            code=code,
            name=f"{market} Companies",
            market=market,
            description=f"All saved {market} companies merged without duplicate tickers.",
            as_of=" / ".join(as_of_values) or None,
            fetched_at=max(fetched) if fetched else None,
            company_count=count,
        )
