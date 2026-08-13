"""Company catalog use cases."""
from __future__ import annotations

from api.repositories.company_catalog_repository import (
    CompanyCatalogQuery,
    CompanyCatalogRecord,
    CompanyCatalogRepository,
    CompanyCatalogFacets,
)


class CompanyCatalogService:
    def __init__(self, repository: CompanyCatalogRepository):
        self._repository = repository

    def list_companies(
        self,
        *,
        country: str | None = None,
        search: str | None = None,
        sector: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[tuple[CompanyCatalogRecord, ...], int, CompanyCatalogFacets]:
        return self._repository.list_companies(CompanyCatalogQuery(
            country=country,
            search=search,
            sector=sector,
            offset=offset,
            limit=limit,
        ))
