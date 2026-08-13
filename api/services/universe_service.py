"""Canonical universe catalog use cases."""
from __future__ import annotations

from api.repositories.universe_repository import (
    UniverseCatalogRecord,
    UniverseRepository,
    UniverseSyncRunPage,
)


class UnknownUniverseError(ValueError):
    pass


class UniverseService:
    def __init__(self, repository: UniverseRepository) -> None:
        self._repository = repository

    def list_universes(self) -> tuple[UniverseCatalogRecord, ...]:
        return self._repository.list_universes()

    def list_sync_runs(
        self,
        universe_id: int,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> UniverseSyncRunPage:
        page = self._repository.list_sync_runs(
            universe_id,
            offset=offset,
            limit=limit,
        )
        if page is None:
            raise UnknownUniverseError(f"Unknown universe: {universe_id}")
        return page
