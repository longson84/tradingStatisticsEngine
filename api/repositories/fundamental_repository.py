"""Persistence-neutral point-in-time fundamentals repository contract."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class FundamentalReportRecord:
    id: int
    ticker: str
    market: str
    source: str
    period_end: date | None
    period_label: str | None
    effective_session_date: date
    fetched_at: datetime
    reporting_currency: str | None
    methodology: str | None


@dataclass(frozen=True)
class FundamentalFactRecord:
    report_id: int
    metric_code: str
    value: Decimal
    unit: str
    currency: str | None
    scale: int
    period_basis: str
    fact_kind: str
    calculation_version: str


@dataclass(frozen=True)
class ProviderValuationRecord:
    effective_session_date: date
    metric_code: str
    value: Decimal
    unit: str
    currency: str | None
    scale: int
    source: str
    methodology: str | None
    fetched_at: datetime


@dataclass(frozen=True)
class FundamentalFactWriteRecord:
    metric_code: str
    value: Decimal
    unit: str
    currency: str | None
    period_basis: str
    fact_kind: str
    source_field: str
    calculation_version: str


@dataclass(frozen=True)
class ProviderValuationWriteRecord:
    metric_code: str
    value: Decimal
    unit: str
    currency: str | None


@dataclass(frozen=True)
class FundamentalReportWriteRecord:
    report_key: str
    period_end: date | None
    period_label: str | None
    fiscal_year: int | None
    fiscal_quarter: int | None
    period_type: str
    effective_session_date: date
    facts: tuple[FundamentalFactWriteRecord, ...]
    valuations: tuple[ProviderValuationWriteRecord, ...]


@dataclass(frozen=True)
class FundamentalWriteBatch:
    market: str
    ticker: str
    source: str
    methodology: str
    fetched_at: datetime
    reports: tuple[FundamentalReportWriteRecord, ...]


@dataclass(frozen=True)
class FundamentalWriteResult:
    report_count: int
    fact_count: int
    valuation_count: int


@dataclass(frozen=True)
class FundamentalStatusRecord:
    universe: str
    market: str
    fetched_at: datetime
    first_effective_date: date
    last_effective_date: date
    symbol_count: int
    report_count: int
    fact_count: int
    valuation_count: int
    sources: tuple[str, ...]
    oldest_fetched_at: datetime | None = None


class FundamentalRepository(Protocol):
    def instrument_exists(self, market: str, ticker: str) -> bool: ...

    def list_reports(
        self, market: str, ticker: str
    ) -> tuple[FundamentalReportRecord, ...]: ...

    def list_facts(
        self, report_ids: tuple[int, ...]
    ) -> tuple[FundamentalFactRecord, ...]: ...

    def list_valuations(
        self, market: str, ticker: str
    ) -> tuple[ProviderValuationRecord, ...]: ...

    def get_universe_status(
        self, universe: str
    ) -> FundamentalStatusRecord | None: ...

    def get_latest_fetched_at(
        self, market: str, ticker: str
    ) -> datetime | None: ...

    def upsert_fundamentals(
        self, batch: FundamentalWriteBatch
    ) -> FundamentalWriteResult: ...

    def create_refresh_run(
        self,
        *,
        job_id: str,
        universe: str,
        source: str,
        provider_version: str | None,
        requested_count: int,
        reused_count: int,
        started_at: datetime,
    ) -> None: ...

    def finish_refresh_run(
        self,
        *,
        job_id: str,
        status: str,
        succeeded_count: int,
        failed_count: int,
        finished_at: datetime,
        error_summary: dict[str, object] | None,
    ) -> None: ...
