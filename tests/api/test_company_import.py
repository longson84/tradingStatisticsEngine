from __future__ import annotations

from datetime import date

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from api.db.company_import import import_company_universes
from api.db.models import (
    Base,
    Company,
    CompanyIdentifier,
    Instrument,
    InstrumentSymbol,
    Universe,
    UniverseMembership,
)


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
        assert apple.company.sector == "Information Technology"
        assert apple.company.industry == "Technology Hardware, Storage & Peripherals"
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


def test_import_reconciles_share_classes_and_stores_symbol_namespaces():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    import_company_universes(engine)

    with Session(engine) as session:
        goog = session.scalar(select(Instrument).where(Instrument.ticker == "GOOG"))
        googl = session.scalar(select(Instrument).where(Instrument.ticker == "GOOGL"))
        assert goog is not None and googl is not None
        assert goog.company_id == googl.company_id
        assert session.scalar(
            select(CompanyIdentifier.value).where(
                CompanyIdentifier.company_id == goog.company_id,
                CompanyIdentifier.namespace == "sec_cik",
            )
        ) == "1652044"

        berkshire = session.scalar(
            select(Instrument).where(Instrument.market == "US", Instrument.ticker == "BRK-B")
        )
        assert berkshire is not None
        symbols = set(session.execute(
            select(InstrumentSymbol.namespace, InstrumentSymbol.symbol).where(
                InstrumentSymbol.instrument_id == berkshire.id
            )
        ))
        assert ("canonical", "BRK-B") in symbols
        assert ("yfinance", "BRK-B") in symbols
        assert ("listing", "BRK.B") in symbols

        assert session.scalar(select(func.count(Company.id))) < session.scalar(
            select(func.count(Instrument.id))
        )


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
            market="US",
            ticker="CNR",
            currency="USD",
            source="exchange",
        )
        instrument.symbols.extend([
            InstrumentSymbol(
                namespace="listing",
                market="US",
                symbol="CEIX",
                valid_to=date(2025, 1, 14),
                is_primary=True,
                source="exchange",
            ),
            InstrumentSymbol(
                namespace="listing",
                market="US",
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
