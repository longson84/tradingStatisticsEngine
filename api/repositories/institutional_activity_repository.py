"""Persistence-neutral contracts for SEC institutional activity."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol

from trading_engine.types import InstitutionalPositionSnapshot


@dataclass(frozen=True)
class InstitutionalManagerWrite:
    sec_cik: str
    legal_name: str
    source: str
    display_name: str | None = None
    is_curated: bool = False


@dataclass(frozen=True)
class InstitutionalFilingWrite:
    manager_id: int
    accession_number: str
    form_type: str
    report_period: date
    filed_at: date
    accepted_at: datetime
    amendment_type: str | None
    source_url: str
    source: str
    fetched_at: datetime


@dataclass(frozen=True)
class InstrumentIdentifierWrite:
    instrument_id: int
    namespace: str
    value: str
    valid_from: date | None
    valid_to: date | None
    source: str
    verified_at: datetime


@dataclass(frozen=True)
class InstitutionalPositionWrite:
    filing_id: int
    source_row_number: int
    instrument_id: int | None
    raw_cusip: str
    issuer_name: str
    title_of_class: str
    reported_value: Decimal
    shares: Decimal
    share_type: str
    put_call: str | None
    investment_discretion: str | None
    voting_sole: Decimal
    voting_shared: Decimal
    voting_none: Decimal
    source: str
    fetched_at: datetime
    reported_value_unit: str = "USD"


class InstitutionalActivityRepository(Protocol):
    def upsert_manager(self, record: InstitutionalManagerWrite) -> int: ...
    def add_identifier(self, record: InstrumentIdentifierWrite) -> int: ...
    def resolve_instrument_id(self, namespace: str, value: str, on: date) -> int | None: ...
    def add_filing(self, record: InstitutionalFilingWrite) -> int: ...
    def add_positions(self, records: Iterable[InstitutionalPositionWrite]) -> int: ...
    def list_report_periods(self, instrument_id: int, limit: int) -> tuple[date, ...]: ...
    def list_effective_common_stock_positions(
        self, instrument_id: int, report_period: date,
    ) -> tuple[InstitutionalPositionSnapshot, ...]: ...
    def list_filing_acceptance(
        self, manager_ids: tuple[int, ...], report_period: date,
    ) -> Mapping[int, datetime]: ...
