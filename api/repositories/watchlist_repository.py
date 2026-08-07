"""Persistence-neutral watchlist repository contract."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class WatchlistMemberRecord:
    ticker: str
    company_name: str
    market: str
    sector: str | None
    industry: str | None
    exchange: str | None
    position: int


@dataclass(frozen=True)
class WatchlistRecord:
    id: int
    name: str
    market: str
    description: str
    created_at: datetime
    updated_at: datetime
    members: tuple[WatchlistMemberRecord, ...]


@dataclass(frozen=True)
class WatchlistSummaryRecord:
    id: int
    name: str
    market: str
    description: str
    member_count: int
    created_at: datetime
    updated_at: datetime


class WatchlistRepository(Protocol):
    def list_watchlists(
        self, market: str | None = None
    ) -> tuple[WatchlistSummaryRecord, ...]: ...

    def get_watchlist(self, watchlist_id: int) -> WatchlistRecord | None: ...

    def name_exists(
        self, market: str, name_key: str, exclude_id: int | None = None
    ) -> bool: ...

    def resolve_instrument_ids(
        self, market: str, tickers: tuple[str, ...]
    ) -> dict[str, int]: ...

    def create_watchlist(
        self, *, name: str, name_key: str, market: str, description: str
    ) -> int: ...

    def update_watchlist(
        self, watchlist_id: int, *, name: str, name_key: str, description: str
    ) -> bool: ...

    def replace_members(
        self, watchlist_id: int, market: str, instrument_ids: tuple[int, ...]
    ) -> None: ...

    def delete_watchlist(self, watchlist_id: int) -> bool: ...
