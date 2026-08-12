"""Persistence-neutral universe catalog contract."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
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


class UniverseRepository(Protocol):
    def list_universes(self) -> tuple[UniverseCatalogRecord, ...]: ...
