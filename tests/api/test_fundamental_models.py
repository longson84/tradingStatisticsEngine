from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.db.models import (
    Base,
    Company,
    FundamentalFact,
    FundamentalReport,
    Instrument,
    ProviderValuationObservation,
    Universe,
)


def _seed_identity(session: Session) -> tuple[Instrument, Universe]:
    instrument = Instrument(
        company=Company(
            display_name="FPT Corporation",
            domicile_country_code="VN",
            source="test",
        ),
        symbol="FPT",
        currency="VND",
        source="test",
    )
    universe = Universe(
        code="VN100",
        name="VN100",
        description="",
        source="test",
    )
    session.add_all([instrument, universe])
    session.flush()
    return instrument, universe


def _report(
    instrument_id: int,
    *,
    report_key: str,
    effective_date: date,
) -> FundamentalReport:
    return FundamentalReport(
        instrument_id=instrument_id,
        source="vnstock-vci-4.0.5",
        report_key=report_key,
        period_end=date(2025, 3, 31),
        fiscal_year=2025,
        fiscal_quarter=1,
        period_type="quarterly",
        effective_session_date=effective_date,
        fetched_at=datetime(2026, 8, 3, tzinfo=UTC),
        reporting_currency="VND",
    )


def test_fundamental_report_has_no_dormant_metadata_columns():
    columns = FundamentalReport.__table__.columns
    assert "provider_report_id" not in columns
    assert "published_at" not in columns
    assert "scope" not in columns
    assert "is_restatement" not in columns
    assert "raw_payload_hash" in columns

    valuation_columns = ProviderValuationObservation.__table__.columns
    assert "observed_at" not in valuation_columns


def test_point_in_time_query_preserves_later_restatement():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        instrument, _ = _seed_identity(session)
        original = _report(
            instrument.id,
            report_key="2025-Q1-original",
            effective_date=date(2025, 4, 25),
        )
        restated = _report(
            instrument.id,
            report_key="2025-Q1-restated",
            effective_date=date(2025, 8, 15),
        )
        session.add_all([original, restated])
        session.flush()
        session.add_all([
            FundamentalFact(
                report_id=original.id,
                metric_code="eps_ttm",
                value=Decimal("10.25"),
                unit="per_share",
                currency="VND",
                scale=1,
                period_basis="ttm",
                fact_kind="provider_derived",
                calculation_version="vci-4.0.5",
            ),
            FundamentalFact(
                report_id=restated.id,
                metric_code="eps_ttm",
                value=Decimal("11.50"),
                unit="per_share",
                currency="VND",
                scale=1,
                period_basis="ttm",
                fact_kind="provider_derived",
                calculation_version="vci-4.0.5",
            ),
        ])
        session.commit()

        def eps_known_on(as_of: date) -> Decimal:
            value = session.scalar(
                select(FundamentalFact.value)
                .join(FundamentalReport)
                .where(
                    FundamentalReport.instrument_id == instrument.id,
                    FundamentalReport.effective_session_date <= as_of,
                    FundamentalFact.metric_code == "eps_ttm",
                )
                .order_by(FundamentalReport.effective_session_date.desc())
                .limit(1)
            )
            assert value is not None
            return value

        assert eps_known_on(date(2025, 5, 1)) == Decimal("10.2500000000")
        assert eps_known_on(date(2025, 8, 15)) == Decimal("11.5000000000")


def test_report_source_key_is_idempotent():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        instrument, _ = _seed_identity(session)
        session.add_all([
            _report(instrument.id, report_key="same", effective_date=date(2025, 4, 25)),
            _report(instrument.id, report_key="same", effective_date=date(2025, 4, 25)),
        ])
        with pytest.raises(IntegrityError):
            session.commit()


def test_provider_valuations_are_sparse_observations_not_daily_facts():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        instrument, _ = _seed_identity(session)
        session.add_all([
            ProviderValuationObservation(
                instrument_id=instrument.id,
                source="vnstock-vci-4.0.5",
                observation_key="2026-Q2",
                effective_session_date=date(2026, 7, 30),
                metric_code="pe",
                value=Decimal("5.46"),
                unit="ratio",
                scale=1,
                methodology="provider-reported comparison only",
                fetched_at=datetime(2026, 8, 3, tzinfo=UTC),
            ),
            ProviderValuationObservation(
                instrument_id=instrument.id,
                source="vnstock-vci-4.0.5",
                observation_key="2026-Q2",
                effective_session_date=date(2026, 7, 30),
                metric_code="pb",
                value=Decimal("1.14"),
                unit="ratio",
                scale=1,
                methodology="provider-reported comparison only",
                fetched_at=datetime(2026, 8, 3, tzinfo=UTC),
            ),
        ])
        session.commit()

        observations = session.scalars(
            select(ProviderValuationObservation).order_by(
                ProviderValuationObservation.metric_code
            )
        ).all()
        assert [(row.metric_code, row.value) for row in observations] == [
            ("pb", Decimal("1.1400000000")),
            ("pe", Decimal("5.4600000000")),
        ]
