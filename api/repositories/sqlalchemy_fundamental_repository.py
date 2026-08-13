"""SQLAlchemy implementation of point-in-time fundamental persistence."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from api.db.models import (
    Company,
    FundamentalFact,
    FundamentalReport,
    Instrument,
    ProviderValuationObservation,
    Universe,
    UniverseMembership,
    Venue,
)
from api.instrument_symbols import canonical_symbol_expression
from api.repositories.fundamental_repository import (
    FundamentalFactRecord,
    FundamentalInstrumentRecord,
    FundamentalReportRecord,
    FundamentalStatusRecord,
    FundamentalWriteBatch,
    FundamentalWriteResult,
    ProviderValuationRecord,
)


class SqlAlchemyFundamentalRepository:
    def __init__(self, session: Session):
        self._session = session

    def get_instrument(
        self, instrument_id: int
    ) -> FundamentalInstrumentRecord | None:
        row = self._session.execute(
            select(
                Instrument.id,
                canonical_symbol_expression(),
                Instrument.currency,
            ).where(
                Instrument.id == instrument_id,
                Instrument.is_active.is_(True),
            )
        ).one_or_none()
        if row is None:
            return None
        return FundamentalInstrumentRecord(
            instrument_id=row.id,
            symbol=row.symbol,
            currency=row.currency,
        )

    def instrument_exists(self, instrument_id: int) -> bool:
        return self._session.scalar(
            select(Instrument.id).where(Instrument.id == instrument_id)
        ) is not None

    def list_reports(
        self, instrument_id: int
    ) -> tuple[FundamentalReportRecord, ...]:
        rows = self._session.execute(
            select(FundamentalReport, canonical_symbol_expression())
            .join(Instrument, Instrument.id == FundamentalReport.instrument_id)
            .where(Instrument.id == instrument_id)
            .order_by(
                FundamentalReport.effective_session_date,
                FundamentalReport.id,
            )
        )
        return tuple(
            FundamentalReportRecord(
                id=report.id,
                instrument_id=report.instrument_id,
                symbol=stored_symbol,
                source=report.source,
                period_end=report.period_end,
                period_label=report.period_label,
                effective_session_date=report.effective_session_date,
                fetched_at=report.fetched_at,
                reporting_currency=report.reporting_currency,
                methodology=report.methodology,
            )
            for report, stored_symbol in rows
        )

    def list_facts(
        self, report_ids: tuple[int, ...]
    ) -> tuple[FundamentalFactRecord, ...]:
        if not report_ids:
            return ()
        rows = self._session.scalars(
            select(FundamentalFact)
            .where(FundamentalFact.report_id.in_(report_ids))
            .order_by(FundamentalFact.report_id, FundamentalFact.metric_code)
        )
        return tuple(
            FundamentalFactRecord(
                report_id=fact.report_id,
                metric_code=fact.metric_code,
                value=fact.value,
                unit=fact.unit,
                currency=fact.currency,
                scale=fact.scale,
                period_basis=fact.period_basis,
                fact_kind=fact.fact_kind,
                calculation_version=fact.calculation_version,
            )
            for fact in rows
        )

    def list_valuations(
        self, instrument_id: int
    ) -> tuple[ProviderValuationRecord, ...]:
        rows = self._session.scalars(
            select(ProviderValuationObservation)
            .join(
                Instrument,
                Instrument.id == ProviderValuationObservation.instrument_id,
            )
            .where(Instrument.id == instrument_id)
            .order_by(
                ProviderValuationObservation.effective_session_date,
                ProviderValuationObservation.id,
            )
        )
        return tuple(
            ProviderValuationRecord(
                effective_session_date=row.effective_session_date,
                metric_code=row.metric_code,
                value=row.value,
                unit=row.unit,
                currency=row.currency,
                scale=row.scale,
                source=row.source,
                methodology=row.methodology,
                fetched_at=row.fetched_at,
            )
            for row in rows
        )

    def get_universe_status(
        self, universe: str
    ) -> FundamentalStatusRecord | None:
        report_filters = (Universe.code == universe,)
        countries = tuple(self._session.scalars(
            select(Company.country_code)
            .select_from(UniverseMembership)
            .join(Instrument, Instrument.id == UniverseMembership.instrument_id)
            .join(Company, Company.id == Instrument.company_id)
            .join(Universe, Universe.id == UniverseMembership.universe_id)
            .where(Universe.code == universe)
            .distinct()
        ))
        if len(countries) != 1:
            return None
        summary = self._session.execute(
            select(
                func.max(FundamentalReport.fetched_at),
                func.min(FundamentalReport.effective_session_date),
                func.max(FundamentalReport.effective_session_date),
                func.count(func.distinct(Instrument.id)),
                func.count(FundamentalReport.id),
            )
            .select_from(FundamentalReport)
            .join(Instrument, Instrument.id == FundamentalReport.instrument_id)
            .join(
                UniverseMembership,
                UniverseMembership.instrument_id == Instrument.id,
            )
            .join(Universe, Universe.id == UniverseMembership.universe_id)
            .where(*report_filters)
        ).one_or_none()
        if summary is None or summary[0] is None:
            return None
        fact_count = int(self._session.scalar(
            select(func.count(FundamentalFact.id))
            .select_from(FundamentalFact)
            .join(FundamentalReport)
            .join(Instrument, Instrument.id == FundamentalReport.instrument_id)
            .join(
                UniverseMembership,
                UniverseMembership.instrument_id == Instrument.id,
            )
            .join(Universe, Universe.id == UniverseMembership.universe_id)
            .where(*report_filters)
        ) or 0)
        valuation_count = int(self._session.scalar(
            select(func.count(ProviderValuationObservation.id))
            .select_from(ProviderValuationObservation)
            .join(
                Instrument,
                Instrument.id == ProviderValuationObservation.instrument_id,
            )
            .join(
                UniverseMembership,
                UniverseMembership.instrument_id == Instrument.id,
            )
            .join(Universe, Universe.id == UniverseMembership.universe_id)
            .where(*report_filters)
        ) or 0)
        sources = tuple(self._session.scalars(
            select(FundamentalReport.source)
            .select_from(FundamentalReport)
            .join(Instrument, Instrument.id == FundamentalReport.instrument_id)
            .join(
                UniverseMembership,
                UniverseMembership.instrument_id == Instrument.id,
            )
            .join(Universe, Universe.id == UniverseMembership.universe_id)
            .where(*report_filters)
            .distinct()
            .order_by(FundamentalReport.source)
        ))
        latest_fetch_by_instrument = (
            select(
                FundamentalReport.instrument_id,
                func.max(FundamentalReport.fetched_at).label("latest_fetched_at"),
            )
            .join(Instrument, Instrument.id == FundamentalReport.instrument_id)
            .join(
                UniverseMembership,
                UniverseMembership.instrument_id == Instrument.id,
            )
            .join(Universe, Universe.id == UniverseMembership.universe_id)
            .where(*report_filters)
            .group_by(FundamentalReport.instrument_id)
            .subquery()
        )
        oldest_fetched_at = self._session.scalar(
            select(func.min(latest_fetch_by_instrument.c.latest_fetched_at))
        )
        return FundamentalStatusRecord(
            universe=universe,
            fetched_at=summary[0],
            first_effective_date=summary[1],
            last_effective_date=summary[2],
            symbol_count=int(summary[3]),
            report_count=int(summary[4]),
            fact_count=fact_count,
            valuation_count=valuation_count,
            sources=sources,
            oldest_fetched_at=oldest_fetched_at,
        )

    def get_latest_fetched_at(
        self, instrument_id: int
    ):
        return self._session.scalar(
            select(func.max(FundamentalReport.fetched_at))
            .where(FundamentalReport.instrument_id == instrument_id)
        )

    def upsert_fundamentals(
        self, batch: FundamentalWriteBatch
    ) -> FundamentalWriteResult:
        instrument_id = batch.instrument_id
        if not self.instrument_exists(instrument_id):
            raise ValueError(f"Unknown instrument: {instrument_id}")
        report_rows = [{
            "instrument_id": instrument_id,
            "source": batch.source,
            "report_key": report.report_key,
            "provider_report_id": None,
            "period_label": report.period_label,
            "period_end": report.period_end,
            "fiscal_year": report.fiscal_year,
            "fiscal_quarter": report.fiscal_quarter,
            "period_type": report.period_type,
            "published_at": None,
            "effective_session_date": report.effective_session_date,
            "fetched_at": batch.fetched_at,
            "reporting_currency": batch.reporting_currency,
            "scope": "unknown",
            "is_restatement": False,
            "raw_payload_hash": None,
            "methodology": batch.methodology,
        } for report in batch.reports]
        if report_rows:
            statement = self._insert(FundamentalReport).values(report_rows)
            excluded = statement.excluded
            self._session.execute(statement.on_conflict_do_update(
                index_elements=(
                    FundamentalReport.instrument_id,
                    FundamentalReport.source,
                    FundamentalReport.report_key,
                ),
                set_={
                    "period_end": excluded.period_end,
                    "period_label": excluded.period_label,
                    "fiscal_year": excluded.fiscal_year,
                    "fiscal_quarter": excluded.fiscal_quarter,
                    "period_type": excluded.period_type,
                    "effective_session_date": excluded.effective_session_date,
                    "fetched_at": excluded.fetched_at,
                    "reporting_currency": excluded.reporting_currency,
                    "methodology": excluded.methodology,
                },
                where=excluded.fetched_at >= FundamentalReport.fetched_at,
            ))
        report_ids = {
            report_key: report_id
            for report_key, report_id in self._session.execute(
                select(FundamentalReport.report_key, FundamentalReport.id).where(
                    FundamentalReport.instrument_id == instrument_id,
                    FundamentalReport.source == batch.source,
                    FundamentalReport.report_key.in_(
                        tuple(report.report_key for report in batch.reports)
                    ),
                )
            )
        } if batch.reports else {}
        fact_rows = [
            {
                "report_id": report_ids[report.report_key],
                "metric_code": fact.metric_code,
                "value": fact.value,
                "unit": fact.unit,
                "currency": fact.currency,
                "scale": 1,
                "period_basis": fact.period_basis,
                "fact_kind": fact.fact_kind,
                "source_field": fact.source_field,
                "calculation_version": fact.calculation_version,
            }
            for report in batch.reports
            for fact in report.facts
        ]
        if fact_rows:
            statement = self._insert(FundamentalFact).values(fact_rows)
            excluded = statement.excluded
            self._session.execute(statement.on_conflict_do_update(
                index_elements=(
                    FundamentalFact.report_id,
                    FundamentalFact.metric_code,
                    FundamentalFact.period_basis,
                    FundamentalFact.fact_kind,
                    FundamentalFact.calculation_version,
                ),
                set_={
                    "value": excluded.value,
                    "unit": excluded.unit,
                    "currency": excluded.currency,
                    "scale": excluded.scale,
                    "source_field": excluded.source_field,
                },
            ))
        valuation_rows = [
            {
                "instrument_id": instrument_id,
                "source": batch.source,
                "observation_key": report.report_key,
                "observed_at": None,
                "effective_session_date": report.effective_session_date,
                "metric_code": valuation.metric_code,
                "value": valuation.value,
                "unit": valuation.unit,
                "currency": valuation.currency,
                "scale": 1,
                "methodology": batch.methodology,
                "fetched_at": batch.fetched_at,
            }
            for report in batch.reports
            for valuation in report.valuations
        ]
        if valuation_rows:
            statement = self._insert(ProviderValuationObservation).values(
                valuation_rows
            )
            excluded = statement.excluded
            self._session.execute(statement.on_conflict_do_update(
                index_elements=(
                    ProviderValuationObservation.instrument_id,
                    ProviderValuationObservation.source,
                    ProviderValuationObservation.observation_key,
                    ProviderValuationObservation.metric_code,
                ),
                set_={
                    "effective_session_date": excluded.effective_session_date,
                    "value": excluded.value,
                    "unit": excluded.unit,
                    "currency": excluded.currency,
                    "scale": excluded.scale,
                    "methodology": excluded.methodology,
                    "fetched_at": excluded.fetched_at,
                },
                where=(
                    excluded.fetched_at
                    >= ProviderValuationObservation.fetched_at
                ),
            ))
        return FundamentalWriteResult(
            report_count=len(report_rows),
            fact_count=len(fact_rows),
            valuation_count=len(valuation_rows),
        )

    def _insert(self, model):
        dialect = self._session.get_bind().dialect.name
        if dialect == "postgresql":
            return postgresql_insert(model)
        if dialect == "sqlite":
            return sqlite_insert(model)
        raise ValueError(f"Unsupported fundamentals dialect: {dialect}")
