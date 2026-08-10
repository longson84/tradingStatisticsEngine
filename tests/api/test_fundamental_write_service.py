from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pytest
from sqlalchemy import create_engine, func, select
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
from api.services.fundamental_write_service import (
    FundamentalWriteError,
    FundamentalWriteService,
)


def _frame(period: str, effective_date: str, eps: float) -> pd.DataFrame:
    quarter = int(period[-1])
    return pd.DataFrame({
        "effective_date": pd.to_datetime([effective_date]),
        "period_end": pd.to_datetime([
            f"2025-{quarter * 3:02d}-{31 if quarter in (1, 4) else 30}"
        ]),
        "period": [period],
        "eps_ttm": [eps],
        "book_value_per_share": [20.0],
        "reported_pe": [10.0],
    })


def _seed_instrument(session: Session) -> None:
    session.add(Instrument(
        company=Company(display_name="Apple", country_code="US", source="test"),
        market="US",
        ticker="AAPL",
        currency="USD",
        source="test",
    ))
    session.commit()


def test_writer_upserts_existing_snapshot_and_preserves_older_history():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _seed_instrument(session)

    first_fetch = datetime(2026, 8, 1, tzinfo=UTC)
    second_fetch = datetime(2026, 8, 3, tzinfo=UTC)
    with Session(engine) as session, session.begin():
        service = FundamentalWriteService(
            SqlAlchemyFundamentalRepository(session)
        )
        result = service.store_provider_frame(
            market="US",
            ticker="AAPL",
            source="yfinance",
            methodology="test method",
            fetched_at=first_fetch,
            frame=_frame("2025-Q1", "2025-05-01", 4.0),
        )
        assert (result.report_count, result.fact_count, result.valuation_count) == (
            1, 2, 1
        )

    with Session(engine) as session, session.begin():
        service = FundamentalWriteService(
            SqlAlchemyFundamentalRepository(session)
        )
        service.store_provider_frame(
            market="US",
            ticker="AAPL",
            source="yfinance",
            methodology="test method",
            fetched_at=second_fetch,
            frame=pd.concat([
                _frame("2025-Q1", "2025-05-01", 4.25),
                _frame("2025-Q2", "2025-08-01", 4.5),
            ], ignore_index=True),
        )

    with Session(engine) as session:
        repository = SqlAlchemyFundamentalRepository(session)
        latest = repository.get_latest_fetched_at("US", "AAPL")
        assert latest is not None
        assert latest.replace(tzinfo=UTC) == second_fetch
        assert session.scalar(select(func.count(FundamentalReport.id))) == 2
        assert session.scalar(select(func.count(FundamentalFact.id))) == 4
        assert session.scalar(
            select(func.count(ProviderValuationObservation.id))
        ) == 2
        q1_eps = session.scalar(
            select(FundamentalFact.value)
            .join(FundamentalReport)
            .where(
                FundamentalReport.period_label == "2025-Q1",
                FundamentalFact.metric_code == "eps_ttm",
            )
        )
        assert float(q1_eps) == 4.25


def test_writer_rejects_empty_provider_result():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _seed_instrument(session)
        service = FundamentalWriteService(
            SqlAlchemyFundamentalRepository(session)
        )

        with pytest.raises(FundamentalWriteError, match="No fundamentals"):
            service.store_provider_frame(
                market="US",
                ticker="AAPL",
                source="yfinance",
                methodology="test method",
                fetched_at=datetime(2026, 8, 3, tzinfo=UTC),
                frame=pd.DataFrame(),
            )
