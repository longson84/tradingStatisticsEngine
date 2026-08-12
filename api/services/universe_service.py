"""Canonical universe catalog use cases."""
from __future__ import annotations

from api.repositories.universe_repository import (
    UniverseCatalogRecord,
    UniverseRepository,
)


class UniverseService:
    def __init__(self, repository: UniverseRepository) -> None:
        self._repository = repository

    def list_universes(self) -> tuple[UniverseCatalogRecord, ...]:
        return self._repository.list_universes()
