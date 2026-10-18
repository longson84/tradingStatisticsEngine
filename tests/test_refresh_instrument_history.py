from __future__ import annotations

from contextlib import contextmanager
from datetime import date, time
from types import SimpleNamespace

import pandas as pd
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from api.db.models import Base, Company, Instrument, PriceRefreshState, Venue
from trading_engine.types import PriceFrame
from scripts import refresh_instrument_history


def test_failed_exact_price_refresh_records_instrument_state(monkeypatch):
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


def test_vn30_refresh_uses_index_acquisition_before_persistence(monkeypatch):
    calls: list[tuple[str, object]] = []
    prices = PriceFrame(
        symbol="VN30",
        data=pd.DataFrame({
            "open": [1_850.0],
            "high": [1_860.0],
            "low": [1_845.0],
            "close": [1_855.41],
            "volume": [100.0],
        }, index=pd.to_datetime(["2026-10-16"])),
        source="vnstock-5.1.0-vci",
    )

    class Loader:
        def load(self, symbol, start, end, **kwargs):
            calls.append(("load", (symbol, start, end, kwargs)))
            return prices

    class Writer:
        def __init__(self, *args):
            pass

        def store_history(self, instrument_id, value, *, fetched_at):
            calls.append(("store", (instrument_id, value)))

    @contextmanager
    def fake_session_scope(engine):
        yield object()

    monkeypatch.setattr(refresh_instrument_history, "VietnamPriceLoader", Loader)
    monkeypatch.setattr(refresh_instrument_history, "InstrumentPriceWriteService", Writer)
    monkeypatch.setattr(refresh_instrument_history, "session_scope", fake_session_scope)
    monkeypatch.setattr(
        refresh_instrument_history,
        "latest_completed_venue_session",
        lambda now, schedule: date(2026, 10, 16),
    )
    instrument = SimpleNamespace(id=30, last_date=None)
    route = SimpleNamespace(
        price_adapter="vnstock",
        provider_symbol="VN30",
        full_history_start=date(2012, 2, 6),
        schedule=object(),
    )

    source = refresh_instrument_history._refresh_market_index(
        object(), instrument, route, "full"
    )

    assert calls[0] == (
        "load",
        ("VN30", date(2012, 2, 6), date(2026, 10, 17), {
            "instrument_kind": "index"
        }),
    )
    assert calls[1] == ("store", (30, prices))
    assert source == "vnstock-5.1.0-vci"
