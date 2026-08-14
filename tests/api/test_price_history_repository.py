from __future__ import annotations

from datetime import UTC, date, datetime, time

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from api.db.models import (
    Base,
    Company,
    Instrument,
    PriceBar,
    PriceBarCoverage,
    Universe,
    UniverseMembership,
    Venue,
)
from api.repositories.price_bar_repository import (
    PriceBarWriteRecord,
)
from api.repositories.sqlalchemy_price_bar_repository import (
    SqlAlchemyPriceBarRepository,
)


def _seed(session: Session) -> None:
    venue = Venue(
        code="HOSE", name="HOSE", venue_type="exchange", country_code="VN",
        timezone_name="Asia/Ho_Chi_Minh", trading_calendar_code="VN_EQUITIES",
        session_cutoff_time=time(15, 15), source="test",
    )
    fpt = Instrument(
        company=Company(
            display_name="FPT",
            domicile_country_code="VN",
            source="test",
        ),
        venue=venue, symbol="FPT", currency="VND", source="test"
    )
    acb = Instrument(
        company=Company(
            display_name="ACB",
            domicile_country_code="VN",
            source="test",
        ),
        venue=venue, symbol="ACB", currency="VND", source="test"
    )
    universe = Universe(
        code="VN100", name="VN100", description="", source="test"
    )
    session.add_all([fpt, acb, universe])
    session.flush()
    session.add_all([
        UniverseMembership(
            universe_id=universe.id, instrument_id=fpt.id, source="test"
        ),
        UniverseMembership(
            universe_id=universe.id, instrument_id=acb.id, source="test"
        ),
    ])
    for instrument, close in ((fpt, 101.0), (acb, 20.0)):
        for trading_date in (date(2026, 7, 30), date(2026, 7, 31)):
            session.add(PriceBar(
                instrument_id=instrument.id,
                trading_date=trading_date,
                open=close - 1,
                high=close + 1,
                low=close - 2,
                close=close,
                volume=1_000.0,
                currency="VND",
                price_scale=1_000,
                price_basis="provider_unspecified",
                source="VCI",
                fetched_at=datetime(2026, 8, 1, tzinfo=UTC),
            ))
        session.add(PriceBarCoverage(
            instrument_id=instrument.id,
            price_basis="provider_unspecified",
            first_date=date(2026, 7, 30),
            last_date=date(2026, 7, 31),
            row_count=2,
            source="VCI",
            fetched_at=datetime(2026, 8, 1, tzinfo=UTC),
        ))
    session.commit()


def test_repository_upsert_updates_existing_bar_without_duplication():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _seed(session)
        repository = SqlAlchemyPriceBarRepository(session)
        fetched_at = datetime(2026, 8, 3, tzinfo=UTC)
        fpt_id = session.scalar(
            select(Instrument.id).where(Instrument.symbol == "FPT")
        )
        affected = repository.upsert_bars((
            PriceBarWriteRecord(
                instrument_id=fpt_id,
                trading_date=date(2026, 7, 31),
                open=102.0,
                high=105.0,
                low=101.0,
                close=104.0,
                volume=2_000.0,
                currency="VND",
                price_scale=1_000,
                price_basis="provider_unspecified",
                source="vnstock-vci",
                fetched_at=fetched_at,
            ),
            PriceBarWriteRecord(
                instrument_id=fpt_id,
                trading_date=date(2026, 8, 3),
                open=104.0,
                high=106.0,
                low=103.0,
                close=105.0,
                volume=3_000.0,
                currency="VND",
                price_scale=1_000,
                price_basis="provider_unspecified",
                source="vnstock-vci",
                fetched_at=fetched_at,
            ),
        ))
        session.commit()

        count = session.scalar(
            select(func.count(PriceBar.id)).where(PriceBar.instrument_id == fpt_id)
        )
        latest = session.scalar(
            select(PriceBar).where(
                PriceBar.instrument_id == fpt_id,
                PriceBar.trading_date == date(2026, 8, 3),
            )
        )
        updated = session.scalar(
            select(PriceBar).where(
                PriceBar.instrument_id == fpt_id,
                PriceBar.trading_date == date(2026, 7, 31),
            )
        )

        assert affected == 2
        assert count == 3
        assert latest is not None and latest.close == 105.0
        assert updated is not None and updated.close == 104.0


def test_repository_writes_equal_tickers_to_the_exact_instrument_id():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        company = Company(
            display_name="Dual Listing",
            domicile_country_code="US",
            source="test",
        )
        venues = [
            Venue(
                code=code,
                name=code,
                venue_type="exchange",
                country_code="US",
                timezone_name="America/New_York",
                trading_calendar_code="US_EQUITIES",
                session_cutoff_time=time(16, 15),
                source="test",
            )
            for code in ("VENUE_ONE", "VENUE_TWO")
        ]
        session.add_all([company, *venues])
        session.flush()
        instruments = [
            Instrument(
                company=company,
                venue=venue,
                symbol="DUAL",
                currency="USD",
                source="test",
            )
            for venue in venues
        ]
        session.add_all(instruments)
        session.flush()

        repository = SqlAlchemyPriceBarRepository(session)
        repository.upsert_bars((PriceBarWriteRecord(
            instrument_id=instruments[1].id,
            trading_date=date(2026, 8, 3),
            open=10.0,
            high=11.0,
            low=9.0,
            close=10.5,
            volume=1_000.0,
            currency="USD",
            price_scale=1,
            price_basis="adjusted",
            source="test",
            fetched_at=datetime(2026, 8, 4, tzinfo=UTC),
        ),))
        session.flush()

        stored_ids = tuple(session.scalars(select(PriceBar.instrument_id)))
        assert stored_ids == (instruments[1].id,)
