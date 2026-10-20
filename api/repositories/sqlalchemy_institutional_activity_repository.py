"""SQLAlchemy persistence for immutable SEC 13F institutional activity."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import distinct, select
from sqlalchemy.orm import Session

from api.db.models import (
    InstitutionalFiling,
    InstitutionalFilingPosition,
    InstitutionalManager,
    Instrument,
    InstrumentIdentifier,
)
from api.repositories.institutional_activity_repository import (
    InstitutionalFilingWrite,
    InstitutionalManagerWrite,
    InstitutionalPositionWrite,
    InstrumentIdentifierWrite,
)
from trading_engine.types import InstitutionalPositionSnapshot


class SqlAlchemyInstitutionalActivityRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert_manager(self, record: InstitutionalManagerWrite) -> int:
        cik = _cik(record.sec_cik)
        row = self._session.scalar(
            select(InstitutionalManager).where(InstitutionalManager.sec_cik == cik)
        )
        if row is None:
            row = InstitutionalManager(
                sec_cik=cik,
                legal_name=_required(record.legal_name, "manager legal_name", 255),
                display_name=_optional(record.display_name, 255),
                is_curated=record.is_curated,
                source=_required(record.source, "manager source", 100),
            )
            self._session.add(row)
            self._session.flush()
        else:
            row.legal_name = _required(record.legal_name, "manager legal_name", 255)
            row.display_name = _optional(record.display_name, 255)
            row.is_curated = record.is_curated
            row.source = _required(record.source, "manager source", 100)
        return row.id

    def add_identifier(self, record: InstrumentIdentifierWrite) -> int:
        if self._session.get(Instrument, record.instrument_id) is None:
            raise ValueError(f"Unknown Instrument: {record.instrument_id}")
        if record.namespace not in {"cusip", "figi", "share_class_figi"}:
            raise ValueError("Unsupported Instrument identifier namespace")
        value = _required(record.value, "identifier value", 64).upper()
        verified_at = _aware(record.verified_at, "identifier verified_at")
        if record.valid_to is not None and record.valid_from is not None and record.valid_to < record.valid_from:
            raise ValueError("Identifier validity range is inverted")
        existing = self._session.scalar(select(InstrumentIdentifier).where(
            InstrumentIdentifier.instrument_id == record.instrument_id,
            InstrumentIdentifier.namespace == record.namespace,
            InstrumentIdentifier.value == value,
            InstrumentIdentifier.valid_from == record.valid_from,
        ))
        if existing is not None:
            return existing.id
        row = InstrumentIdentifier(
            instrument_id=record.instrument_id,
            namespace=record.namespace,
            value=value,
            valid_from=record.valid_from,
            valid_to=record.valid_to,
            source=_required(record.source, "identifier source", 100),
            verified_at=verified_at,
        )
        self._session.add(row)
        self._session.flush()
        return row.id

    def resolve_instrument_id(self, namespace: str, value: str, on: date) -> int | None:
        rows = tuple(self._session.scalars(select(InstrumentIdentifier).where(
            InstrumentIdentifier.namespace == namespace,
            InstrumentIdentifier.value == value.strip().upper(),
            (InstrumentIdentifier.valid_from.is_(None) | (InstrumentIdentifier.valid_from <= on)),
            (InstrumentIdentifier.valid_to.is_(None) | (InstrumentIdentifier.valid_to >= on)),
        )))
        ids = {row.instrument_id for row in rows}
        if len(ids) > 1:
            raise ValueError(f"Ambiguous verified {namespace} mapping: {value}")
        return next(iter(ids), None)

    def add_filing(self, record: InstitutionalFilingWrite) -> int:
        if self._session.get(InstitutionalManager, record.manager_id) is None:
            raise ValueError(f"Unknown institutional manager: {record.manager_id}")
        accession = _required(record.accession_number, "filing accession", 32)
        accepted_at = _aware(record.accepted_at, "filing accepted_at")
        fetched_at = _aware(record.fetched_at, "filing fetched_at")
        if record.form_type not in {"13F-HR", "13F-HR/A"}:
            raise ValueError("Unsupported institutional filing form")
        if record.amendment_type not in {None, "restatement", "new_holdings"}:
            raise ValueError("Unsupported institutional amendment type")
        existing = self._session.scalar(select(InstitutionalFiling).where(
            InstitutionalFiling.accession_number == accession
        ))
        values = dict(
            manager_id=record.manager_id,
            accession_number=accession,
            form_type=record.form_type,
            report_period=record.report_period,
            filed_at=record.filed_at,
            accepted_at=accepted_at,
            amendment_type=record.amendment_type,
            source_url=_required(record.source_url, "filing source_url", 1000),
            source=_required(record.source, "filing source", 100),
            fetched_at=fetched_at,
        )
        if existing is not None:
            if any(_utc_if_datetime(getattr(existing, name)) != value for name, value in values.items()):
                raise ValueError(f"Filing accession conflicts with stored record: {accession}")
            return existing.id
        row = InstitutionalFiling(**values)
        self._session.add(row)
        self._session.flush()
        return row.id

    def add_positions(self, records: Iterable[InstitutionalPositionWrite]) -> int:
        added = 0
        for record in records:
            values = self._position_values(record)
            existing = self._session.scalar(select(InstitutionalFilingPosition).where(
                InstitutionalFilingPosition.filing_id == record.filing_id,
                InstitutionalFilingPosition.source_row_number == record.source_row_number,
            ))
            if existing is not None:
                if any(_utc_if_datetime(getattr(existing, name)) != value for name, value in values.items()):
                    raise ValueError("Institutional position conflicts with stored source row")
                continue
            self._session.add(InstitutionalFilingPosition(**values))
            added += 1
        self._session.flush()
        return added

    def list_report_periods(self, instrument_id: int, limit: int) -> tuple[date, ...]:
        if limit < 1:
            return ()
        return tuple(self._session.scalars(
            select(distinct(InstitutionalFiling.report_period))
            .join(
                InstitutionalFilingPosition,
                InstitutionalFilingPosition.filing_id == InstitutionalFiling.id,
            )
            .where(
                InstitutionalFilingPosition.instrument_id == instrument_id,
                InstitutionalFilingPosition.put_call.is_(None),
                InstitutionalFilingPosition.share_type == "SH",
            )
            .order_by(InstitutionalFiling.report_period.desc())
            .limit(limit)
        ))

    def list_effective_common_stock_positions(
        self, instrument_id: int, report_period: date,
    ) -> tuple[InstitutionalPositionSnapshot, ...]:
        filings = tuple(self._session.scalars(
            select(InstitutionalFiling)
            .where(InstitutionalFiling.report_period == report_period)
            .order_by(InstitutionalFiling.manager_id, InstitutionalFiling.accepted_at)
        ))
        effective_ids: set[int] = set()
        by_manager: dict[int, list[InstitutionalFiling]] = defaultdict(list)
        for filing in filings:
            by_manager[filing.manager_id].append(filing)
        for manager_filings in by_manager.values():
            reset = [row for row in manager_filings if row.amendment_type != "new_holdings"]
            if not reset:
                continue
            base = max(reset, key=lambda row: row.accepted_at)
            effective_ids.add(base.id)
            effective_ids.update(
                row.id for row in manager_filings
                if row.amendment_type == "new_holdings" and row.accepted_at > base.accepted_at
            )
        if not effective_ids:
            return ()
        rows = tuple(self._session.execute(
            select(InstitutionalFilingPosition, InstitutionalFiling)
            .join(InstitutionalFiling, InstitutionalFiling.id == InstitutionalFilingPosition.filing_id)
            .where(
                InstitutionalFilingPosition.filing_id.in_(effective_ids),
                InstitutionalFilingPosition.instrument_id == instrument_id,
                InstitutionalFilingPosition.put_call.is_(None),
                InstitutionalFilingPosition.share_type == "SH",
            )
        ).all())
        grouped: dict[int, list[tuple[InstitutionalFilingPosition, InstitutionalFiling]]] = defaultdict(list)
        for position, filing in rows:
            grouped[filing.manager_id].append((position, filing))
        return tuple(
            InstitutionalPositionSnapshot(
                manager_id=manager_id,
                instrument_id=instrument_id,
                report_period=report_period,
                accepted_at=max(_as_utc(filing.accepted_at) for _, filing in values),
                shares=sum((position.shares for position, _ in values), Decimal(0)),
                security_type="common_stock",
            )
            for manager_id, values in sorted(grouped.items())
        )

    def list_filing_acceptance(
        self, manager_ids: tuple[int, ...], report_period: date,
    ) -> dict[int, datetime]:
        if not manager_ids:
            return {}
        rows = self._session.scalars(select(InstitutionalFiling).where(
            InstitutionalFiling.manager_id.in_(manager_ids),
            InstitutionalFiling.report_period == report_period,
        ))
        result: dict[int, datetime] = {}
        for row in rows:
            accepted = _as_utc(row.accepted_at)
            result[row.manager_id] = max(result.get(row.manager_id, accepted), accepted)
        return result

    def _position_values(self, record: InstitutionalPositionWrite) -> dict[str, object]:
        if self._session.get(InstitutionalFiling, record.filing_id) is None:
            raise ValueError(f"Unknown institutional filing: {record.filing_id}")
        if record.instrument_id is not None and self._session.get(Instrument, record.instrument_id) is None:
            raise ValueError(f"Unknown Instrument: {record.instrument_id}")
        if record.source_row_number < 1:
            raise ValueError("Institutional position source row must be positive")
        for name in ("reported_value", "shares", "voting_sole", "voting_shared", "voting_none"):
            value = getattr(record, name)
            if not isinstance(value, Decimal) or not value.is_finite():
                raise ValueError(f"Institutional position {name} must be a finite Decimal")
            if value < 0 or (name == "shares" and value == 0):
                raise ValueError(f"Institutional position {name} is outside its valid range")
        put_call = record.put_call.upper() if record.put_call else None
        if put_call not in {None, "PUT", "CALL"} or record.share_type not in {"SH", "PRN"}:
            raise ValueError("Unsupported institutional position security fields")
        return dict(
            filing_id=record.filing_id,
            source_row_number=record.source_row_number,
            instrument_id=record.instrument_id,
            raw_cusip=_required(record.raw_cusip, "position CUSIP", 16).upper(),
            issuer_name=_required(record.issuer_name, "position issuer", 255),
            title_of_class=_required(record.title_of_class, "position class", 100),
            reported_value=record.reported_value,
            reported_value_unit=_required(record.reported_value_unit, "position value unit", 16),
            shares=record.shares,
            share_type=record.share_type,
            put_call=put_call,
            investment_discretion=_optional(record.investment_discretion, 32),
            voting_sole=record.voting_sole,
            voting_shared=record.voting_shared,
            voting_none=record.voting_none,
            source=_required(record.source, "position source", 100),
            fetched_at=_aware(record.fetched_at, "position fetched_at"),
        )


def _required(value: str, label: str, maximum: int) -> str:
    normalized = value.strip() if isinstance(value, str) else ""
    if not normalized or len(normalized) > maximum:
        raise ValueError(f"{label} is required and must be at most {maximum} characters")
    return normalized


def _optional(value: str | None, maximum: int) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > maximum:
        raise ValueError(f"Optional value must be at most {maximum} characters")
    return normalized


def _cik(value: str) -> str:
    normalized = value.strip()
    if not normalized.isdigit() or len(normalized) > 10:
        raise ValueError("SEC CIK must contain at most 10 digits")
    return normalized.zfill(10)


def _aware(value: datetime, label: str) -> datetime:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
    return value.astimezone(UTC)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _utc_if_datetime(value):
    return _as_utc(value) if isinstance(value, datetime) else value
