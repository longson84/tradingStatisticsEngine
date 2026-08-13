"""Persistence-neutral scope resolution for data operations."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal, Protocol


DataOperationScopeType = Literal["universe", "watchlist", "instrument"]


@dataclass(frozen=True)
class DataOperationInstrumentRecord:
    id: int
    symbol: str
    instrument_type: str
    company_id: int | None
    venue_code: str | None
    price_basis: str
    first_date: date | None
    last_date: date | None
    row_count: int
    coverage_source: str | None
    coverage_fetched_at: datetime | None
    attempted_through: date | None
    returned_through: date | None
    refresh_outcome: str | None
    primary_source: str | None
    selected_source: str | None
    refresh_detail: str | None
    attempted_at: datetime | None
    fundamental_fetched_at: datetime | None = None


@dataclass(frozen=True)
class DataOperationScopeRecord:
    scope_type: DataOperationScopeType
    scope_id: str
    name: str
    instruments: tuple[DataOperationInstrumentRecord, ...]


class DataOperationRepository(Protocol):
    def get_scope(
        self, scope_type: DataOperationScopeType, scope_id: str
    ) -> DataOperationScopeRecord | None: ...
