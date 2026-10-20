"""Persistence-neutral contracts for SEC institutional activity."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol

from trading_engine.types import InstitutionalPositionSnapshot


class AmbiguousInstrumentIdentifierError(ValueError):
    """Verified identifier ranges resolve to multiple Instruments."""


@dataclass(frozen=True)
class InstitutionalActivityInstrument:
    instrument_id: int
    symbol: str
    instrument_type: str
    venue_code: str | None
    venue_country_code: str | None
    is_active: bool


@dataclass(frozen=True)
class InstitutionalManagerRecord:
    manager_id: int
    sec_cik: str
    name: str
    is_curated: bool


@dataclass(frozen=True)
class InstitutionalFilingMetadata:
    manager_id: int
    report_period: date
    accepted_at: datetime
    availability_precision: str
    source_url: str


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
    amendment_number: int
    source_url: str
    source: str
    fetched_at: datetime
    availability_precision: str = "accepted_at"
    is_complete: bool = True


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
    mapping_status: str
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
    raw_figi: str | None = None
    reported_value_unit: str = "USD"


@dataclass(frozen=True)
class InstitutionalPositionRejectionWrite:
    filing_id: int | None
    accession_number: str | None
    source_row_number: int
    reason: str
    raw_payload: dict[str, str]
    source: str
    fetched_at: datetime


class InstitutionalActivityRepository(Protocol):
    def get_instrument(self, instrument_id: int) -> InstitutionalActivityInstrument | None: ...
    def upsert_manager(self, record: InstitutionalManagerWrite) -> int: ...
    def add_identifier(self, record: InstrumentIdentifierWrite) -> int: ...
    def resolve_instrument_id(self, namespace: str, value: str, on: date) -> int | None: ...
    def get_effective_identifier(
        self, instrument_id: int, namespace: str, on: date,
    ) -> str | None: ...
    def add_filing(self, record: InstitutionalFilingWrite) -> int: ...
    def add_positions(self, records: Iterable[InstitutionalPositionWrite]) -> int: ...
    def add_position_rejections(
        self, records: Iterable[InstitutionalPositionRejectionWrite],
    ) -> int: ...
    def set_filing_completeness(self, filing_id: int, is_complete: bool) -> None: ...
    def list_report_periods(self, instrument_id: int, limit: int) -> tuple[date, ...]: ...
    def list_effective_common_stock_positions(
        self, instrument_id: int, report_period: date,
    ) -> tuple[InstitutionalPositionSnapshot, ...]: ...
    def list_filing_acceptance(
        self, manager_ids: tuple[int, ...], report_period: date,
    ) -> Mapping[int, datetime]: ...
    def list_managers(
        self, manager_ids: tuple[int, ...],
    ) -> Mapping[int, InstitutionalManagerRecord]: ...
    def list_effective_filing_metadata(
        self, manager_ids: tuple[int, ...], report_period: date, instrument_id: int,
    ) -> Mapping[int, InstitutionalFilingMetadata]: ...
