from __future__ import annotations

from datetime import time

import pandas as pd
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from api.db.models import Base, Company, FundamentalFact, FundamentalReport, Instrument, Venue
from scripts import refresh_instrument_fundamentals


def test_exact_instrument_fundamentals_write_and_incremental_reuse(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session, session.begin():
        instrument = Instrument(
            company=Company(
                display_name="Microsoft",
                domicile_country_code="US",
                source="test",
            ),
            venue=Venue(
                code="NASDAQ",
                name="Nasdaq",
                venue_type="exchange",
                country_code="US",
                timezone_name="America/New_York",
                trading_calendar_code="US_EQUITIES",
                session_cutoff_time=time(16, 15),
                source="test",
            ),
            symbol="MSFT",
            instrument_type="common_stock",
            currency="USD",
            source="test",
            is_active=True,
        )
        session.add(instrument)
        session.flush()
        instrument_id = instrument.id

    calls: list[str] = []

    def fetch(symbol, adapter, **kwargs):
        calls.append(f"{symbol}:{adapter}")
        return (
            pd.DataFrame([{
                "effective_date": "2026-08-12",
                "period_end": "2026-06-30",
                "period": "2026-Q2",
                "revenue_ttm": 1000,
            }]),
            "yfinance",
            "test methodology",
        )

    monkeypatch.setattr(
        refresh_instrument_fundamentals,
        "fetch_provider_fundamentals",
        fetch,
    )

    first = refresh_instrument_fundamentals.refresh_instrument_fundamentals(
        instrument_id, "full", engine=engine
    )
    second = refresh_instrument_fundamentals.refresh_instrument_fundamentals(
        instrument_id, "incremental", engine=engine
    )

    assert calls == ["MSFT:yfinance"]
    assert first == "stored 1 reports and 1 facts from yfinance"
    assert second == "reused recent canonical fundamentals"
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(FundamentalReport)) == 1
        assert session.scalar(select(func.count()).select_from(FundamentalFact)) == 1
