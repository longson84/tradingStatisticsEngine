"""Read-only canonical venue catalog use cases."""
from __future__ import annotations

from api.repositories.venue_repository import VenueRecord, VenueRepository


class VenueService:
    def __init__(self, repository: VenueRepository) -> None:
        self._repository = repository

    def list_venues(self) -> tuple[VenueRecord, ...]:
        return self._repository.list_venues()
