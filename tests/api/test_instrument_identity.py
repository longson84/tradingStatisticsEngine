from __future__ import annotations

from datetime import date

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from api.db.models import Base, Company, Instrument, InstrumentSymbol


def test_instrument_model_has_no_legacy_note_column():
    assert "note" not in Instrument.__table__.columns
    assert "notes" not in Instrument.__table__.columns
    assert "ticker" not in Instrument.__table__.columns


def test_symbol_history_preserves_ticker_rename_without_changing_instrument():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        instrument = Instrument(
            company=Company(
                display_name="Core Natural Resources",
                country_code="US",
                source="sec",
            ),
            ticker="CNR",
            currency="USD",
            source="exchange",
        )
        instrument.symbols.extend([
            InstrumentSymbol(
                namespace="listing",
                symbol="CEIX",
                valid_to=date(2025, 1, 14),
                is_primary=True,
                source="exchange",
            ),
            InstrumentSymbol(
                namespace="listing",
                symbol="CNR",
                valid_from=date(2025, 1, 15),
                is_primary=True,
                source="exchange",
            ),
        ])
        session.add(instrument)
        session.commit()

        stored = session.scalar(select(Instrument).where(Instrument.ticker == "CNR"))
        assert stored is not None
        assert {symbol.symbol for symbol in stored.symbols} == {"CEIX", "CNR"}
        assert "providers" not in Base.metadata.tables
