from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from api.db.models import (
    Base,
    Company,
    FundamentalFact,
    FundamentalReport,
    Instrument,
    ProviderValuationObservation,
)
from api.repositories.sqlalchemy_fundamental_repository import (
    SqlAlchemyFundamentalRepository,
)


FETCHED_AT = datetime(2026, 8, 3, tzinfo=UTC)


def _seed(session: Session) -> FundamentalReport:
    instrument = Instrument(
        company=Company(
            display_name="FPT Corporation", country_code="VN", source="test"
        ),
        symbol="FPT",
        currency="VND",
        source="test",
    )
    session.add(instrument)
    session.flush()
    report = FundamentalReport(
        instrument_id=instrument.id,
        source="vnstock-vci-4.0.5",
        report_key="2025-Q1",
        period_end=date(2025, 3, 31),
        period_label="2025-Q1",
        fiscal_year=2025,
        fiscal_quarter=1,
        period_type="quarterly",
        effective_session_date=date(2025, 4, 25),
        fetched_at=FETCHED_AT,
        reporting_currency="VND",
        methodology="VCI normalized point-in-time fundamentals",
    )
    session.add(report)
    session.flush()
    session.add_all([
        FundamentalFact(
            report_id=report.id,
            metric_code="eps_ttm",
            value=Decimal("1234.5"),
            unit="per_share",
            currency="VND",
            scale=1,
            period_basis="ttm",
            fact_kind="provider_derived",
            calculation_version="vci-4.0.5",
        ),
        FundamentalFact(
            report_id=report.id,
            metric_code="shares_outstanding",
            value=Decimal("1000000"),
            unit="shares",
            currency=None,
            scale=1,
            period_basis="instant",
            fact_kind="reported",
            calculation_version="vci-4.0.5",
        ),
        ProviderValuationObservation(
            instrument_id=instrument.id,
            source="vnstock-vci-4.0.5",
            observation_key="2025-Q1",
            effective_session_date=date(2025, 4, 25),
            metric_code="pe",
            value=Decimal("11.2"),
            unit="ratio",
            scale=1,
            methodology="provider-reported comparison only",
            fetched_at=FETCHED_AT,
        ),
    ])
    session.commit()
    return report


def test_repository_reads_symbol_fundamentals_in_stable_order():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        report = _seed(session)
        repository = SqlAlchemyFundamentalRepository(session)
        instrument_id = report.instrument_id

        reports = repository.list_reports(instrument_id)
        facts = repository.list_facts((report.id,))
        valuations = repository.list_valuations(instrument_id)

        assert repository.get_instrument(instrument_id) is not None
        assert repository.instrument_exists(instrument_id)
        assert not repository.instrument_exists(instrument_id + 1)
        assert reports[0].period_label == "2025-Q1"
        assert reports[0].methodology == "VCI normalized point-in-time fundamentals"
        assert [fact.metric_code for fact in facts] == [
            "eps_ttm",
            "shares_outstanding",
        ]
        assert [(row.metric_code, row.value) for row in valuations] == [
            ("pe", Decimal("11.2000000000")),
        ]
