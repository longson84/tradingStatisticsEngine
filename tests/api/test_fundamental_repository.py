from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from api.db.models import (
    Base,
    Company,
    FundamentalFact,
    FundamentalRefreshRun,
    FundamentalReport,
    Instrument,
    ProviderValuationObservation,
    Universe,
    UniverseMembership,
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
        market="VN",
        ticker="FPT",
        currency="VND",
        source="test",
    )
    universe = Universe(
        code="VN100",
        name="VN100",
        market="VN",
        description="",
        source="test",
    )
    session.add_all([instrument, universe])
    session.flush()
    session.add(UniverseMembership(
        universe_id=universe.id,
        instrument_id=instrument.id,
        source="test",
    ))
    report = FundamentalReport(
        instrument_id=instrument.id,
        source="vnstock-vci-4.0.5",
        report_key="2025-Q1",
        period_end=date(2025, 3, 31),
        period_label="2025-Q1",
        fiscal_year=2025,
        fiscal_quarter=1,
        period_type="quarterly",
        published_at=datetime(2025, 4, 25, tzinfo=UTC),
        effective_session_date=date(2025, 4, 25),
        fetched_at=FETCHED_AT,
        reporting_currency="VND",
        scope="consolidated",
        is_restatement=False,
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
            observed_at=datetime(2025, 4, 25, tzinfo=UTC),
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

        reports = repository.list_reports("VN", "FPT")
        facts = repository.list_facts((report.id,))
        valuations = repository.list_valuations("VN", "FPT")

        assert repository.instrument_exists("VN", "FPT")
        assert not repository.instrument_exists("US", "FPT")
        assert reports[0].period_label == "2025-Q1"
        assert reports[0].methodology == "VCI normalized point-in-time fundamentals"
        assert [fact.metric_code for fact in facts] == [
            "eps_ttm",
            "shares_outstanding",
        ]
        assert [(row.metric_code, row.value) for row in valuations] == [
            ("pe", Decimal("11.2000000000")),
        ]


def test_repository_aggregates_universe_status():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _seed(session)
        repository = SqlAlchemyFundamentalRepository(session)

        status = repository.get_universe_status("VN100")

        assert status is not None
        assert status.market == "VN"
        assert status.first_effective_date == date(2025, 4, 25)
        assert status.last_effective_date == date(2025, 4, 25)
        assert status.symbol_count == 1
        assert status.report_count == 1
        assert status.fact_count == 2
        assert status.valuation_count == 1
        assert status.sources == ("vnstock-vci-4.0.5",)
        assert repository.get_universe_status("VN30") is None


def test_repository_records_durable_refresh_run():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _seed(session)
        repository = SqlAlchemyFundamentalRepository(session)
        repository.create_refresh_run(
            job_id="job-1",
            universe="VN100",
            source="vnstock-vci-4.0.5",
            provider_version="4.0.5",
            requested_count=100,
            reused_count=30,
            started_at=FETCHED_AT,
        )
        session.commit()
        repository.finish_refresh_run(
            job_id="job-1",
            status="completed",
            succeeded_count=68,
            failed_count=2,
            finished_at=datetime(2026, 8, 3, 1, tzinfo=UTC),
            error_summary={"errors": [{"symbol": "AAA"}]},
        )
        session.commit()

        run = session.scalar(select(FundamentalRefreshRun))
        assert run is not None
        assert run.status == "completed"
        assert run.requested_count == 100
        assert run.reused_count == 30
        assert run.succeeded_count == 68
        assert run.failed_count == 2
        assert run.error_summary == {"errors": [{"symbol": "AAA"}]}
