"""Persistence-neutral records for live Universe synchronization."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol


class UniverseSyncRejectedError(ValueError):
    """Raised when a snapshot fails a synchronization safety invariant."""


@dataclass(frozen=True)
class UniverseSyncIdentifier:
    namespace: str
    value: str


@dataclass(frozen=True)
class UniverseSyncMember:
    symbol: str
    listing_symbol: str
    company_name: str
    sector: str | None
    industry: str | None
    venue_code: str
    identifiers: tuple[UniverseSyncIdentifier, ...]


@dataclass(frozen=True)
class UniverseSyncSnapshot:
    code: str
    name: str
    country_code: str
    description: str
    effective_date: date | None
    fetched_at: datetime
    source: str
    members: tuple[UniverseSyncMember, ...]


@dataclass(frozen=True)
class UniverseSyncResult:
    universe_code: str
    received_count: int
    added_count: int
    removed_count: int
    unchanged_count: int
    metadata_change_count: int
    dry_run: bool = False


class UniverseSyncRepository(Protocol):
    def preview(
        self,
        snapshots: tuple[UniverseSyncSnapshot, ...],
        *,
        force: bool,
    ) -> tuple[UniverseSyncResult, ...]: ...

    def synchronize(
        self,
        snapshots: tuple[UniverseSyncSnapshot, ...],
        *,
        force: bool,
        started_at: datetime,
    ) -> tuple[UniverseSyncResult, ...]: ...

    def record_failures(
        self,
        *,
        universe_codes: tuple[str, ...],
        source: str,
        started_at: datetime,
        error: str,
    ) -> None: ...
