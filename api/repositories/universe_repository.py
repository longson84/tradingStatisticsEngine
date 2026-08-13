"""Persistence-neutral universe catalog contract."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol


@dataclass(frozen=True)
class UniverseCatalogRecord:
    id: int
    code: str
    name: str
    description: str
    source: str
    as_of: str | None
    fetched_at: datetime | None
    instrument_count: int
    active_instrument_count: int
    instrument_types: tuple[str, ...]
    venue_codes: tuple[str, ...]


@dataclass(frozen=True)
class UniverseSyncRunRecord:
    id: int
    universe_code: str
    source: str
    status: str
    started_at: datetime
    finished_at: datetime
    effective_date: date | None
    received_count: int
    added_count: int
    removed_count: int
    unchanged_count: int
    error: str | None


@dataclass(frozen=True)
class UniverseSyncRunPage:
    universe_id: int
    universe_code: str
    runs: tuple[UniverseSyncRunRecord, ...]
    total: int
    offset: int
    limit: int


class UniverseRepository(Protocol):
    def list_universes(self) -> tuple[UniverseCatalogRecord, ...]: ...

    def list_sync_runs(
        self,
        universe_id: int,
        *,
        offset: int,
        limit: int,
    ) -> UniverseSyncRunPage | None: ...
