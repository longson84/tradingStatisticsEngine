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
    InstitutionalPositionRejection,
    InstitutionalManager,
    Instrument,
    InstrumentIdentifier,
    Venue,
)
from api.instrument_symbols import canonical_symbol_expression
from api.repositories.institutional_activity_repository import (
    AmbiguousInstrumentIdentifierError,
    InstitutionalActivityInstrument,
    InstitutionalFilingWrite,
    InstitutionalFilingMetadata,
    InstitutionalManagerRecord,
    InstitutionalManagerWrite,
    InstitutionalPositionWrite,
    InstitutionalPositionRejectionWrite,
    InstrumentIdentifierWrite,
)
from trading_engine.types import InstitutionalPositionSnapshot


class SqlAlchemyInstitutionalActivityRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_instrument(self, instrument_id: int) -> InstitutionalActivityInstrument | None:
        row = self._session.execute(
            select(
                Instrument.id,
                canonical_symbol_expression(),
                Instrument.instrument_type,
                Instrument.is_active,
                Venue.code.label("venue_code"),
                Venue.country_code.label("venue_country_code"),
            )
            .outerjoin(Venue, Venue.id == Instrument.venue_id)
            .where(Instrument.id == instrument_id)
        ).one_or_none()
        if row is None:
            return None
        return InstitutionalActivityInstrument(
            row.id, row.symbol, row.instrument_type, row.venue_code,
            row.venue_country_code, row.is_active,
        )

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
            raise AmbiguousInstrumentIdentifierError(
                f"Ambiguous verified {namespace} mapping: {value}"
            )
        return next(iter(ids), None)

    def get_effective_identifier(
        self, instrument_id: int, namespace: str, on: date,
    ) -> str | None:
        rows = tuple(self._session.scalars(select(InstrumentIdentifier.value).where(
            InstrumentIdentifier.instrument_id == instrument_id,
            InstrumentIdentifier.namespace == namespace,
            (InstrumentIdentifier.valid_from.is_(None) | (InstrumentIdentifier.valid_from <= on)),
            (InstrumentIdentifier.valid_to.is_(None) | (InstrumentIdentifier.valid_to >= on)),
        )))
        if len(set(rows)) > 1:
            raise ValueError(
                f"Instrument {instrument_id} has ambiguous effective {namespace} identifiers"
            )
        return next(iter(rows), None)

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
        if record.availability_precision not in {"accepted_at", "filing_date_conservative"}:
            raise ValueError("Unsupported filing availability precision")
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
            availability_precision=record.availability_precision,
            amendment_type=record.amendment_type,
            amendment_number=record.amendment_number,
            is_complete=record.is_complete,
            source_url=_required(record.source_url, "filing source_url", 1000),
            source=_required(record.source, "filing source", 100),
            fetched_at=fetched_at,
        )
        if existing is not None:
            immutable_values = {
                name: value for name, value in values.items()
                if name not in {"fetched_at", "is_complete"}
            }
            if any(
                _utc_if_datetime(getattr(existing, name)) != value
                for name, value in immutable_values.items()
            ):
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
                immutable_values = {
                    name: value for name, value in values.items() if name != "fetched_at"
                }
                if any(
                    _utc_if_datetime(getattr(existing, name)) != value
                    for name, value in immutable_values.items()
                ):
                    raise ValueError("Institutional position conflicts with stored source row")
                continue
            self._session.add(InstitutionalFilingPosition(**values))
            added += 1
        self._session.flush()
        return added

    def add_position_rejections(
        self, records: Iterable[InstitutionalPositionRejectionWrite],
    ) -> int:
        added = 0
        for record in records:
            existing = self._session.scalar(select(InstitutionalPositionRejection).where(
                InstitutionalPositionRejection.filing_id == record.filing_id,
                InstitutionalPositionRejection.accession_number == record.accession_number,
                InstitutionalPositionRejection.source_row_number == record.source_row_number,
            ))
            if existing is not None:
                continue
            self._session.add(InstitutionalPositionRejection(
                filing_id=record.filing_id,
                accession_number=_optional(record.accession_number, 32),
                source_row_number=record.source_row_number,
                reason=_required(record.reason, "rejection reason", 1000),
                raw_payload=record.raw_payload,
                source=_required(record.source, "rejection source", 100),
                fetched_at=_aware(record.fetched_at, "rejection fetched_at"),
            ))
            added += 1
        self._session.flush()
        return added

    def set_filing_completeness(self, filing_id: int, is_complete: bool) -> None:
        filing = self._session.get(InstitutionalFiling, filing_id)
        if filing is None:
            raise ValueError(f"Unknown institutional filing: {filing_id}")
        filing.is_complete = is_complete

    def list_report_periods(self, instrument_id: int, limit: int) -> tuple[date, ...]:
        if limit < 1:
            return ()
        prior_holder_managers = (
            select(InstitutionalFiling.manager_id)
            .join(
                InstitutionalFilingPosition,
                InstitutionalFilingPosition.filing_id == InstitutionalFiling.id,
            )
            .where(
                InstitutionalFilingPosition.instrument_id == instrument_id,
                InstitutionalFilingPosition.put_call.is_(None),
                InstitutionalFilingPosition.share_type == "SH",
            )
            .distinct()
        )
        return tuple(self._session.scalars(
            select(distinct(InstitutionalFiling.report_period))
            .where(
                InstitutionalFiling.manager_id.in_(prior_holder_managers),
                InstitutionalFiling.is_complete.is_(True),
            )
            .order_by(InstitutionalFiling.report_period.desc())
            .limit(limit)
        ))

    def list_effective_common_stock_positions(
        self, instrument_id: int, report_period: date,
    ) -> tuple[InstitutionalPositionSnapshot, ...]:
        effective_by_manager = self._effective_filings(report_period)
        effective_ids = {
            row.id for rows in effective_by_manager.values() for row in rows
        }
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

    def _effective_filings(
        self, report_period: date,
    ) -> dict[int, tuple[InstitutionalFiling, ...]]:
        filings = tuple(self._session.scalars(
            select(InstitutionalFiling)
            .where(
                InstitutionalFiling.report_period == report_period,
                InstitutionalFiling.is_complete.is_(True),
            )
            .order_by(
                InstitutionalFiling.manager_id,
                InstitutionalFiling.accepted_at,
                InstitutionalFiling.amendment_number,
                InstitutionalFiling.id,
            )
        ))
        by_manager: dict[int, list[InstitutionalFiling]] = defaultdict(list)
        for filing in filings:
            by_manager[filing.manager_id].append(filing)
        result: dict[int, tuple[InstitutionalFiling, ...]] = {}
        for manager_id, manager_filings in by_manager.items():
            reset = [row for row in manager_filings if row.amendment_type != "new_holdings"]
            if not reset:
                continue
            revision_key = lambda row: (
                _as_utc(row.accepted_at), row.amendment_number, row.id,
            )
            base = max(reset, key=revision_key)
            selected = [base]
            selected.extend(
                row for row in manager_filings
                if row.amendment_type == "new_holdings"
                and revision_key(row) > revision_key(base)
            )
            result[manager_id] = tuple(selected)
        return result

    def list_filing_acceptance(
        self, manager_ids: tuple[int, ...], report_period: date,
    ) -> dict[int, datetime]:
        if not manager_ids:
            return {}
        rows = self._session.scalars(select(InstitutionalFiling).where(
            InstitutionalFiling.manager_id.in_(manager_ids),
            InstitutionalFiling.report_period == report_period,
            InstitutionalFiling.is_complete.is_(True),
        ))
        result: dict[int, datetime] = {}
        for row in rows:
            accepted = _as_utc(row.accepted_at)
            result[row.manager_id] = max(result.get(row.manager_id, accepted), accepted)
        return result

    def list_managers(
        self, manager_ids: tuple[int, ...],
    ) -> dict[int, InstitutionalManagerRecord]:
        if not manager_ids:
            return {}
        rows = self._session.scalars(select(InstitutionalManager).where(
            InstitutionalManager.id.in_(manager_ids)
        ))
        return {
            row.id: InstitutionalManagerRecord(
                row.id, row.sec_cik, row.display_name or row.legal_name, row.is_curated,
            )
            for row in rows
        }

    def list_effective_filing_metadata(
        self, manager_ids: tuple[int, ...], report_period: date, instrument_id: int,
    ) -> dict[int, InstitutionalFilingMetadata]:
        if not manager_ids:
            return {}
        effective = self._effective_filings(report_period)
        result = {}
        for manager_id in manager_ids:
            manager_filings = effective.get(manager_id, ())
            if not manager_filings:
                continue
            filing_ids = tuple(row.id for row in manager_filings)
            contributing_ids = set(self._session.scalars(
                select(InstitutionalFilingPosition.filing_id).where(
                    InstitutionalFilingPosition.filing_id.in_(filing_ids),
                    InstitutionalFilingPosition.instrument_id == instrument_id,
                    InstitutionalFilingPosition.put_call.is_(None),
                    InstitutionalFilingPosition.share_type == "SH",
                )
            ))
            candidates = [
                row for row in manager_filings if row.id in contributing_ids
            ] or list(manager_filings)
            row = max(candidates, key=lambda item: (
                _as_utc(item.accepted_at), item.amendment_number, item.id,
            ))
            result[row.manager_id] = InstitutionalFilingMetadata(
                row.manager_id, row.report_period, _as_utc(row.accepted_at),
                row.availability_precision, row.source_url,
            )
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
            mapping_status=record.mapping_status,
            raw_cusip=_required(record.raw_cusip, "position CUSIP", 16).upper(),
            raw_figi=_optional(record.raw_figi, 32),
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
