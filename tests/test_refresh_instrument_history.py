from __future__ import annotations

from datetime import time

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from api.db.models import Base, Company, Instrument, PriceRefreshState, Venue
from scripts import refresh_instrument_history


def test_failed_exact_price_refresh_records_instrument_state(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session, session.begin():
        instrument = Instrument(
            company=Company(
                display_name="Microsoft",
                country_code="US",
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

    def fail(*args, **kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(refresh_instrument_history, "_refresh_equity", fail)

    with pytest.raises(RuntimeError, match="provider unavailable"):
        refresh_instrument_history.refresh_instrument(
            instrument_id,
            "full",
            engine=engine,
            emit_progress=False,
        )

    with Session(engine) as session:
        state = session.scalar(select(PriceRefreshState))
    assert state is not None
    assert state.instrument_id == instrument_id
    assert state.price_basis == "adjusted"
    assert state.outcome == "failed"
    assert state.primary_source == "yfinance"
    assert state.detail == "provider unavailable"
