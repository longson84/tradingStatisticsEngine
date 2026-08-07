from __future__ import annotations

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from api.db.company_import import import_company_universes
from api.db.models import Base, Instrument, Universe, UniverseMembership


def test_company_import_is_idempotent_and_preserves_many_to_many_membership():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    first = import_company_universes(engine)
    second = import_company_universes(engine)

    assert first == second
    assert {row.universe: row.stored_members for row in first.universes} == {
        "US100": 103,
        "US2000": 1954,
        "US500": 503,
        "US30": 30,
        "VN30": 30,
        "VNMID": 70,
        "VN100": 100,
        "VNSML": 215,
        "VNALL": 315,
    }
    with Session(engine) as session:
        apple = session.scalar(
            select(Instrument).where(
                Instrument.market == "US", Instrument.ticker == "AAPL"
            )
        )
        assert apple is not None
        assert apple.sector == "Information Technology"
        assert apple.industry == "Technology Hardware, Storage & Peripherals"
        assert apple.exchange == "NASDAQ"
        apple_lists = set(session.scalars(
            select(Universe.code)
            .join(UniverseMembership)
            .where(UniverseMembership.instrument_id == apple.id)
        ))
        assert apple_lists == {"US100", "US500", "US30"}

        fpt = session.scalar(
            select(Instrument).where(
                Instrument.market == "VN", Instrument.ticker == "FPT"
            )
        )
        assert fpt is not None
        fpt_lists = set(session.scalars(
            select(Universe.code)
            .join(UniverseMembership)
            .where(UniverseMembership.instrument_id == fpt.id)
        ))
        assert fpt_lists == {"VN30", "VN100", "VNALL"}

        membership_count = session.scalar(select(func.count(UniverseMembership.id)))
        assert membership_count == 3320


def test_instrument_model_has_no_note_column():
    assert "note" not in Instrument.__table__.columns
    assert "notes" not in Instrument.__table__.columns
