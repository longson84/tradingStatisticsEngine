"""Database-only Institutional Activity projection for an exact US equity."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal

from api.repositories.institutional_activity_repository import (
    InstitutionalActivityRepository,
)
from trading_engine.institutional import derive_institutional_position_changes


InstitutionalActivityStatus = Literal[
    "available", "unknown_instrument", "unsupported_instrument",
    "missing_identifier", "no_stored_filings",
]


@dataclass(frozen=True)
class InstitutionalActivityHistory:
    report_period: date
    holder_count: int
    total_shares: Decimal


@dataclass(frozen=True)
class InstitutionalActivityPositionChange:
    manager_id: int
    manager_name: str
    is_curated: bool
    action: str
    previous_shares: Decimal
    current_shares: Decimal
    share_change: Decimal
    percentage_change: Decimal | None
    report_period: date
    available_at: datetime
    availability_precision: str
    source_url: str


@dataclass(frozen=True)
class InstitutionalActivityHolder:
    manager_id: int
    manager_name: str
    is_curated: bool
    shares: Decimal
    report_period: date
    available_at: datetime
    availability_precision: str
    source_url: str


@dataclass(frozen=True)
class InstitutionalActivityData:
    status: InstitutionalActivityStatus
    message: str | None
    instrument_id: int
    symbol: str | None
    instrument_type: str | None
    venue_code: str | None
    formula_version: str
    latest_report_period: date | None
    latest_available_at: datetime | None
    action_counts: dict[str, int]
    history: tuple[InstitutionalActivityHistory, ...]
    changes: tuple[InstitutionalActivityPositionChange, ...]
    current_holders: tuple[InstitutionalActivityHolder, ...]


class InstitutionalActivityService:
    def __init__(self, repository: InstitutionalActivityRepository) -> None:
        self._repository = repository

    def get_activity(
        self, instrument_id: int, quarters: int = 8,
    ) -> InstitutionalActivityData:
        if not 1 <= quarters <= 20:
            raise ValueError("quarters must be between 1 and 20")
        instrument = self._repository.get_instrument(instrument_id)
        if instrument is None:
            return self._unavailable(
                "unknown_instrument", instrument_id, None, None, None,
                f"Unknown instrument: {instrument_id}",
            )
        if (
            not instrument.is_active
            or instrument.instrument_type != "common_stock"
            or instrument.venue_country_code != "US"
        ):
            return self._unavailable(
                "unsupported_instrument", instrument_id, instrument.symbol,
                instrument.instrument_type, instrument.venue_code,
                "Institutional Activity supports active US common stocks only",
            )
        if self._repository.get_effective_identifier(
            instrument_id, "cusip", date.today()
        ) is None:
            return self._unavailable(
                "missing_identifier", instrument_id, instrument.symbol,
                instrument.instrument_type, instrument.venue_code,
                "No verified CUSIP mapping is stored for this Instrument",
            )
        periods = self._repository.list_report_periods(instrument_id, quarters)
        if not periods:
            return self._unavailable(
                "no_stored_filings", instrument_id, instrument.symbol,
                instrument.instrument_type, instrument.venue_code,
                "No stored SEC 13F positions are available for this Instrument",
            )

        positions = {
            period: self._repository.list_effective_common_stock_positions(
                instrument_id, period,
            )
            for period in periods
        }
        history = tuple(
            InstitutionalActivityHistory(
                period, len(positions[period]),
                sum((row.shares for row in positions[period]), Decimal(0)),
            )
            for period in reversed(periods)
        )
        latest_period = periods[0]
        current = positions[latest_period]
        previous = positions[periods[1]] if len(periods) > 1 else ()
        previous_manager_ids = tuple({row.manager_id for row in previous})
        acceptance = self._repository.list_filing_acceptance(
            previous_manager_ids, latest_period,
        )
        calculated = (
            derive_institutional_position_changes(
                previous,
                current,
                current_report_period=latest_period,
                current_filing_accepted_at=acceptance,
            )
            if len(periods) > 1 else ()
        )
        manager_ids = tuple(sorted({
            row.manager_id for row in (*previous, *current)
        }))
        managers = self._repository.list_managers(manager_ids)
        metadata = self._repository.list_effective_filing_metadata(
            manager_ids, latest_period,
        )
        changes = tuple(
            InstitutionalActivityPositionChange(
                manager_id=row.manager_id,
                manager_name=managers[row.manager_id].name,
                is_curated=managers[row.manager_id].is_curated,
                action=row.action,
                previous_shares=row.previous_shares,
                current_shares=row.current_shares,
                share_change=row.share_change,
                percentage_change=row.percentage_change,
                report_period=row.report_period,
                available_at=row.available_at,
                availability_precision=metadata[row.manager_id].availability_precision,
                source_url=metadata[row.manager_id].source_url,
            )
            for row in calculated
        )
        holders = tuple(sorted((
            InstitutionalActivityHolder(
                manager_id=row.manager_id,
                manager_name=managers[row.manager_id].name,
                is_curated=managers[row.manager_id].is_curated,
                shares=row.shares,
                report_period=row.report_period,
                available_at=row.accepted_at,
                availability_precision=metadata[row.manager_id].availability_precision,
                source_url=metadata[row.manager_id].source_url,
            )
            for row in current
        ), key=lambda row: (-row.shares, row.manager_name)))
        counts = {action: 0 for action in (
            "new", "added", "unchanged", "reduced", "exited",
        )}
        for row in changes:
            counts[row.action] += 1
        latest_available = max(
            (row.accepted_at for row in current), default=None,
        )
        return InstitutionalActivityData(
            status="available", message=None,
            instrument_id=instrument_id, symbol=instrument.symbol,
            instrument_type=instrument.instrument_type, venue_code=instrument.venue_code,
            formula_version="institutional_position_change_v1",
            latest_report_period=latest_period,
            latest_available_at=latest_available,
            action_counts=counts, history=history, changes=changes,
            current_holders=holders,
        )

    @staticmethod
    def _unavailable(
        status: InstitutionalActivityStatus,
        instrument_id: int,
        symbol: str | None,
        instrument_type: str | None,
        venue_code: str | None,
        message: str,
    ) -> InstitutionalActivityData:
        return InstitutionalActivityData(
            status=status, message=message, instrument_id=instrument_id,
            symbol=symbol, instrument_type=instrument_type, venue_code=venue_code,
            formula_version="institutional_position_change_v1",
            latest_report_period=None, latest_available_at=None,
            action_counts={action: 0 for action in (
                "new", "added", "unchanged", "reduced", "exited",
            )},
            history=(), changes=(), current_holders=(),
        )
