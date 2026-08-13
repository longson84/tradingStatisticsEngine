"""Persistence-neutral watchlist repository contract."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class WatchlistMemberRecord:
    instrument_id: int
    symbol: str
    instrument_type: str
    company_id: int | None
    company_name: str | None
    sector: str | None
    industry: str | None
    venue_code: str | None
    venue_name: str | None
    base_asset: str | None
    quote_asset: str | None
    currency: str
    position: int


@dataclass(frozen=True)
class WatchlistRecord:
    id: int
    name: str
    description: str
    created_at: datetime
    updated_at: datetime
    members: tuple[WatchlistMemberRecord, ...]

    @property
    def instrument_types(self) -> tuple[str, ...]:
        return tuple(sorted({member.instrument_type for member in self.members}))

    @property
    def equity_count(self) -> int:
        return sum(member.company_id is not None for member in self.members)

    @property
    def crypto_spot_count(self) -> int:
        return sum(member.instrument_type == "spot" for member in self.members)

    @property
    def reference_rate_count(self) -> int:
        return sum(member.instrument_type == "reference_rate" for member in self.members)

    @property
    def market_index_count(self) -> int:
        return sum(member.instrument_type == "market_index" for member in self.members)

@dataclass(frozen=True)
class WatchlistSummaryRecord:
    id: int
    name: str
    description: str
    member_count: int
    instrument_types: tuple[str, ...]
    equity_count: int
    crypto_spot_count: int
    reference_rate_count: int
    market_index_count: int
    created_at: datetime
    updated_at: datetime


class WatchlistRepository(Protocol):
    def list_watchlists(self) -> tuple[WatchlistSummaryRecord, ...]: ...

    def get_watchlist(self, watchlist_id: int) -> WatchlistRecord | None: ...

    def name_exists(self, name_key: str, exclude_id: int | None = None) -> bool: ...

    def resolve_active_instrument_ids(
        self, instrument_ids: tuple[int, ...]
    ) -> set[int]: ...

    def create_watchlist(
        self, *, name: str, name_key: str, description: str
    ) -> int: ...

    def update_watchlist(
        self, watchlist_id: int, *, name: str, name_key: str, description: str
    ) -> bool: ...

    def replace_members(
        self, watchlist_id: int, instrument_ids: tuple[int, ...]
    ) -> None: ...

    def delete_watchlist(self, watchlist_id: int) -> bool: ...
