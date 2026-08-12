"""Public canonical universe contracts."""
from __future__ import annotations

from datetime import datetime

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
