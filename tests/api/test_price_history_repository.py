from __future__ import annotations

from datetime import UTC, date, datetime

import pandas as pd
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
)
from api.repositories.price_bar_repository import PriceBarQuery, SymbolPriceBarQuery
from api.repositories.price_bar_repository import (
    PriceBarWriteRecord,
    PriceRefreshStateWriteRecord,
)
from api.repositories.sqlalchemy_price_bar_repository import (
    SqlAlchemyPriceBarRepository,
)


def _seed(session: Session) -> None:
    fpt = Instrument(
        company=Company(display_name="FPT", country_code="VN", source="test"),
        market="VN", ticker="FPT", currency="VND", source="test"
    )
    acb = Instrument(
        company=Company(display_name="ACB", country_code="VN", source="test"),
        market="VN", ticker="ACB", currency="VND", source="test"
    )
    universe = Universe(
        code="VN100", name="VN100", market="VN", description="", source="test"
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


def test_repository_streams_deterministic_universe_rows_with_date_filter():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _seed(session)
        repository = SqlAlchemyPriceBarRepository(session)

        rows = tuple(repository.iter_bars(PriceBarQuery(
            universe="VN100",
            price_basis="provider_unspecified",
            start=date(2026, 7, 31),
        )))

        assert repository.get_universe_market("VN100") == "VN"
        assert repository.get_latest_date(
            "VN100", "provider_unspecified"
        ) == date(2026, 7, 31)
        assert [(row.ticker, row.trading_date) for row in rows] == [
            ("ACB", date(2026, 7, 31)),
            ("FPT", date(2026, 7, 31)),
        ]


def test_repository_loads_close_only_market_health_matrix():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _seed(session)
        repository = SqlAlchemyPriceBarRepository(session)

        closes = repository.load_close_matrix(PriceBarQuery(
            universe="VN100",
            price_basis="provider_unspecified",
            start=date(2026, 7, 31),
        ))

        assert list(closes.columns) == ["FPT", "ACB"]
        assert list(closes.index.date) == [date(2026, 7, 31)]
        assert closes.loc[pd.Timestamp("2026-07-31"), "FPT"] == 101.0
        assert closes.loc[pd.Timestamp("2026-07-31"), "ACB"] == 20.0


def test_repository_limits_symbol_history_to_selected_universe_and_basis():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _seed(session)
        repository = SqlAlchemyPriceBarRepository(session)

        rows = tuple(repository.iter_bars(PriceBarQuery(
            universe="VN100",
            ticker="FPT",
            price_basis="provider_unspecified",
        )))
        wrong_basis = tuple(repository.iter_bars(PriceBarQuery(
            universe="VN100", ticker="FPT", price_basis="adjusted"
        )))

        assert [row.close for row in rows] == [101.0, 101.0]
        assert wrong_basis == ()


def test_repository_reads_canonical_symbol_without_requiring_a_universe():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _seed(session)
        repository = SqlAlchemyPriceBarRepository(session)

        coverage = repository.get_symbol_coverage(
            "VN", "FPT", "provider_unspecified"
        )
        rows = tuple(repository.iter_symbol_bars(SymbolPriceBarQuery(
            market="VN",
            ticker="FPT",
            price_basis="provider_unspecified",
        )))

        assert repository.instrument_exists("VN", "FPT")
        assert not repository.instrument_exists("US", "FPT")
        assert coverage is not None and coverage.last_date == date(2026, 7, 31)
        assert [row.close for row in rows] == [101.0, 101.0]


def test_repository_lists_canonical_coverages_for_explicit_market_tickers():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _seed(session)
        watchlist_only = Instrument(
            company=Company(display_name="PNJ", country_code="VN", source="test"),
            market="VN",
            ticker="PNJ",
            currency="VND",
            source="test",
        )
        session.add(watchlist_only)
        session.flush()
        session.add(PriceBarCoverage(
            instrument_id=watchlist_only.id,
            price_basis="provider_unspecified",
            first_date=date(2020, 1, 2),
            last_date=date(2026, 8, 3),
            row_count=1_600,
            source="vnstock-vci",
            fetched_at=datetime(2026, 8, 4, tzinfo=UTC),
        ))
        session.commit()

        rows = SqlAlchemyPriceBarRepository(session).list_symbol_coverages(
            "VN", ("FPT", "PNJ"), "provider_unspecified"
        )

        assert [(row.ticker, row.last_date) for row in rows] == [
            ("FPT", date(2026, 7, 31)),
            ("PNJ", date(2026, 8, 3)),
        ]


def test_repository_upsert_updates_existing_bar_without_duplication():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _seed(session)
        repository = SqlAlchemyPriceBarRepository(session)
        fetched_at = datetime(2026, 8, 3, tzinfo=UTC)
        affected = repository.upsert_bars((
            PriceBarWriteRecord(
                market="VN",
                ticker="FPT",
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
                market="VN",
                ticker="FPT",
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

        fpt_id = session.scalar(select(Instrument.id).where(Instrument.ticker == "FPT"))
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


def test_repository_reports_status_and_clears_market_rows():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _seed(session)
        repository = SqlAlchemyPriceBarRepository(session)

        status = repository.get_status(
            "VN100", "provider_unspecified", date(2026, 7, 31)
        )

        assert status is not None
        assert status.market == "VN"
        assert status.first_date == date(2026, 7, 30)
        assert status.last_date == date(2026, 7, 31)
        assert status.symbol_count == 2
        assert status.universe_symbol_count == 2
        assert status.current_symbol_count == 2
        assert status.stale_symbol_count == 0
        assert status.missing_symbol_count == 0
        assert status.coverage_through == date(2026, 7, 31)
        assert status.row_count == 4
        assert status.sources == ("VCI",)
        assert repository.list_market_universes("VN") == ("VN100",)

        assert repository.delete_market_bars("VN") == 4
        assert repository.get_status(
            "VN100", "provider_unspecified", date(2026, 7, 31)
        ) is None


def test_repository_status_distinguishes_current_stale_and_missing_symbols():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _seed(session)
        universe = session.scalar(select(Universe).where(Universe.code == "VN100"))
        missing = Instrument(
            company=Company(display_name="Missing", country_code="VN", source="test"),
            market="VN", ticker="MISSING", currency="VND", source="test"
        )
        session.add(missing)
        session.flush()
        session.add(UniverseMembership(
            universe_id=universe.id,
            instrument_id=missing.id,
            source="test",
        ))
        session.commit()

        status = SqlAlchemyPriceBarRepository(session).get_status(
            "VN100", "provider_unspecified", date(2026, 8, 3)
        )

        assert status is not None
        assert status.universe_symbol_count == 3
        assert status.symbol_count == 2
        assert status.current_symbol_count == 0
        assert status.stale_symbol_count == 2
        assert status.missing_symbol_count == 1
        assert status.coverage_through == date(2026, 7, 31)


def test_repository_status_separates_checked_no_new_bar_from_stale():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _seed(session)
        repository = SqlAlchemyPriceBarRepository(session)
        repository.upsert_refresh_states([
            PriceRefreshStateWriteRecord(
                market="VN",
                ticker="FPT",
                price_basis="provider_unspecified",
                attempted_through=date(2026, 8, 3),
                returned_through=date(2026, 7, 31),
                outcome="checked_no_new_bar",
                primary_source="vnstock-kbs",
                selected_source="vnstock-vci",
                detail="both providers checked",
                attempted_at=datetime(2026, 8, 3, tzinfo=UTC),
            ),
            PriceRefreshStateWriteRecord(
                market="VN",
                ticker="ACB",
                price_basis="provider_unspecified",
                attempted_through=date(2026, 8, 3),
                returned_through=None,
                outcome="failed",
                primary_source="vnstock-kbs",
                selected_source=None,
                detail="both providers failed",
                attempted_at=datetime(2026, 8, 3, tzinfo=UTC),
            ),
        ])
        session.commit()

        status = repository.get_status(
            "VN100", "provider_unspecified", date(2026, 8, 3)
        )

        assert status is not None
        assert status.current_symbol_count == 0
        assert status.checked_no_new_bar_count == 1
        assert status.stale_symbol_count == 1
        assert status.failed_refresh_symbol_count == 1
