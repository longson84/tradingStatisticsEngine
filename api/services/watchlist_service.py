"""Watchlist use cases independent from FastAPI and SQLAlchemy."""
from __future__ import annotations

from api.repositories.watchlist_repository import (
    WatchlistRecord,
    WatchlistRepository,
    WatchlistSummaryRecord,
)


class UnknownWatchlistError(ValueError):
    pass


class DuplicateWatchlistError(ValueError):
    pass


class InvalidWatchlistInstrumentError(ValueError):
    pass


class WatchlistService:
    def __init__(self, repository: WatchlistRepository):
        self._repository = repository

    def list_watchlists(self) -> tuple[WatchlistSummaryRecord, ...]:
        return self._repository.list_watchlists()

    def get_watchlist(self, watchlist_id: int) -> WatchlistRecord:
        watchlist = self._repository.get_watchlist(watchlist_id)
        if watchlist is None:
            raise UnknownWatchlistError(f"Unknown watchlist: {watchlist_id}")
        return watchlist

    def create_watchlist(
        self,
        *,
        name: str,
        description: str = "",
        instrument_ids: list[int] | tuple[int, ...] = (),
    ) -> WatchlistRecord:
        normalized_name, name_key = _name(name)
        normalized_ids = _instrument_ids(instrument_ids)
        if self._repository.name_exists(name_key):
            raise DuplicateWatchlistError(
                f"A watchlist named {normalized_name!r} already exists"
            )
        self._validate_members(normalized_ids)
        watchlist_id = self._repository.create_watchlist(
            name=normalized_name,
            name_key=name_key,
            description=description.strip(),
        )
        self._repository.replace_members(watchlist_id, normalized_ids)
        return self.get_watchlist(watchlist_id)

    def update_watchlist(
        self,
        watchlist_id: int,
        *,
        name: str,
        description: str = "",
        instrument_ids: list[int] | tuple[int, ...] = (),
    ) -> WatchlistRecord:
        self.get_watchlist(watchlist_id)
        normalized_name, name_key = _name(name)
        if self._repository.name_exists(name_key, exclude_id=watchlist_id):
            raise DuplicateWatchlistError(
                f"A watchlist named {normalized_name!r} already exists"
            )
        normalized_ids = _instrument_ids(instrument_ids)
        self._validate_members(normalized_ids)
        if not self._repository.update_watchlist(
            watchlist_id,
            name=normalized_name,
            name_key=name_key,
            description=description.strip(),
        ):
            raise UnknownWatchlistError(f"Unknown watchlist: {watchlist_id}")
        self._repository.replace_members(watchlist_id, normalized_ids)
        return self.get_watchlist(watchlist_id)

    def delete_watchlist(self, watchlist_id: int) -> None:
        if not self._repository.delete_watchlist(watchlist_id):
            raise UnknownWatchlistError(f"Unknown watchlist: {watchlist_id}")

    def _validate_members(self, instrument_ids: tuple[int, ...]) -> None:
        resolved = self._repository.resolve_active_instrument_ids(instrument_ids)
        missing = tuple(value for value in instrument_ids if value not in resolved)
        if missing:
            rendered = ", ".join(str(value) for value in missing)
            raise InvalidWatchlistInstrumentError(
                f"These instrument IDs are unknown or inactive: {rendered}"
            )


def _name(value: str) -> tuple[str, str]:
    name = " ".join(value.split())
    if not name:
        raise ValueError("Watchlist name is required")
    return name, name.casefold()


def _instrument_ids(values: list[int] | tuple[int, ...]) -> tuple[int, ...]:
    seen: set[int] = set()
    result: list[int] = []
    for value in values:
        if value > 0 and value not in seen:
            seen.add(value)
            result.append(value)
    return tuple(result)
