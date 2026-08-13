"""Public canonical universe contracts."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


class UniverseCatalogResponse(BaseModel):
    id: int
    code: str
    name: str
    description: str
    source: str
    as_of: str | None = None
    fetched_at: datetime | None = None
    instrument_count: int
    active_instrument_count: int
    instrument_types: list[str]
    venue_codes: list[str]


class UniverseListResponse(BaseModel):
    universes: list[UniverseCatalogResponse]


class UniverseSyncRunResponse(BaseModel):
    id: int
    universe_code: str
    source: str
    status: Literal["succeeded", "failed"]
    started_at: datetime
    finished_at: datetime
    effective_date: date | None
    received_count: int
    added_count: int
    removed_count: int
    unchanged_count: int
    error: str | None


class UniverseSyncRunPageResponse(BaseModel):
    universe_id: int
    universe_code: str
    runs: list[UniverseSyncRunResponse]
    total: int
    offset: int
    limit: int
