from __future__ import annotations

from datetime import UTC, date, datetime, time

import pandas as pd
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.db.models import Asset, Base, Company, Instrument, PriceBar, Venue
from api.main import app
from api.repositories.sqlalchemy_price_bar_repository import (
    SqlAlchemyPriceBarRepository,
)
from api.repositories.sqlalchemy_reference_rate_repository import (
    SqlAlchemyReferenceRateRepository,
)
from api.routes.reference_rates import list_reference_rates
from api.services.reference_rate_service import ReferenceRateService
from trading_engine.types import PriceFrame


def _engine():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def test_reference_rate_catalog_creates_assets_without_company_or_venue():
    engine = _engine()
    with Session(engine) as session, session.begin():
        results = ReferenceRateService(
            SqlAlchemyReferenceRateRepository(session)
        ).sync_catalog()

    assert [row.symbol for row in results] == ["BTC-USD", "ETH-USD"]
    assert {row.base_asset for row in results} == {"BTC", "ETH"}
    assert {row.quote_asset for row in results} == {"USD"}
    with Session(engine) as session:
        assert session.scalar(select(func.count(Company.id))) == 0
        assert session.scalar(select(func.count(Venue.id))) == 0
        assert session.scalar(select(func.count(Asset.id))) == 3
        instruments = session.scalars(
            select(Instrument).order_by(Instrument.ticker)
        ).all()
        assert [row.ticker for row in instruments] == ["BTC-USD", "ETH-USD"]
        assert {row.instrument_type for row in instruments} == {"reference_rate"}
        assert all(row.company_id is None for row in instruments)
        assert all(row.venue_id is None for row in instruments)
        assert {row.base_asset.canonical_code for row in instruments} == {"BTC", "ETH"}
        assert {row.quote_asset.canonical_code for row in instruments} == {"USD"}


def test_reference_rate_catalog_upgrades_code_only_asset_name():
    engine = _engine()
    with Session(engine) as session, session.begin():
        session.add(Asset(
            canonical_code="BTC",
            name="BTC",
            asset_type="crypto",
            is_active=True,
            source="binance_spot_exchange_info",
        ))
    with Session(engine) as session, session.begin():
        ReferenceRateService(
            SqlAlchemyReferenceRateRepository(session)
        ).sync_catalog(("BTC-USD",))
    with Session(engine) as session:
        btc = session.scalar(select(Asset).where(Asset.canonical_code == "BTC"))
        assert btc is not None and btc.name == "Bitcoin"


def test_reference_rate_identity_constraint_rejects_a_venue():
    engine = _engine()
    with Session(engine) as session, session.begin():
        btc = Asset(
            canonical_code="BTC",
            name="Bitcoin",
            asset_type="crypto",
            is_active=True,
            source="test",
        )
        usd = Asset(
            canonical_code="USD",
            name="United States Dollar",
            asset_type="fiat",
            is_active=True,
            source="test",
        )
        venue = Venue(
            code="TEST",
            name="Test Venue",
            venue_type="exchange",
            timezone_name="UTC",
            trading_calendar_code="CRYPTO_24_7",
            session_cutoff_time=time(0, 0),
            is_active=True,
            source="test",
        )
        session.add_all((btc, usd, venue))
        session.flush()
        session.add(Instrument(
            venue_id=venue.id,
            base_asset_id=btc.id,
            quote_asset_id=usd.id,
            settlement_asset_id=usd.id,
            ticker="BTC-USD",
            instrument_type="reference_rate",
            currency="USD",
            is_active=True,
            source="test",
        ))
        try:
            session.flush()
        except IntegrityError:
            pass
        else:  # pragma: no cover - proves the database constraint is active
            raise AssertionError("reference-rate instrument accepted a venue")


def test_reference_rate_history_uses_canonical_price_bars_and_usd_quote():
    engine = _engine()
    with Session(engine) as session, session.begin():
        instrument = ReferenceRateService(
            SqlAlchemyReferenceRateRepository(session)
        ).sync_catalog(("BTC-USD",))[0]
    prices = PriceFrame(
        symbol="BTC-USD",
        source="yfinance",
        data=pd.DataFrame(
            {
                "open": [100.0, 105.0],
                "high": [110.0, 115.0],
                "low": [90.0, 100.0],
                "close": [105.0, 112.0],
                "volume": [1_000.0, 1_200.0],
            },
            index=pd.to_datetime(["2026-08-08", "2026-08-09"]),
        ),
    )
    with Session(engine) as session, session.begin():
        result = ReferenceRateService(
            SqlAlchemyReferenceRateRepository(session),
            SqlAlchemyPriceBarRepository(session),
        ).store_history(
            instrument,
            prices,
            fetched_at=datetime(2026, 8, 10, tzinfo=UTC),
        )
        assert result.input_rows == 2
        assert result.rejected_rows == 0
        assert result.stored_rows == 2

    with Session(engine) as session:
        bars = session.scalars(select(PriceBar).order_by(PriceBar.trading_date)).all()
        assert [bar.trading_date for bar in bars] == [
            date(2026, 8, 8),
            date(2026, 8, 9),
        ]
        assert {bar.currency for bar in bars} == {"USD"}
        assert {bar.price_basis for bar in bars} == {"provider_unspecified"}
        assert {bar.source for bar in bars} == {"yahoo_finance"}


def test_reference_rate_route_paginates_filters_and_exposes_no_venue():
    engine = _engine()
    with Session(engine) as session, session.begin():
        ReferenceRateService(
            SqlAlchemyReferenceRateRepository(session)
        ).sync_catalog()
    with Session(engine) as session:
        response = list_reference_rates(
            ReferenceRateService(SqlAlchemyReferenceRateRepository(session)),
            search="bitcoin",
            base_asset="BTC",
            quote_asset="USD",
            status="active",
            offset=0,
            limit=50,
        )

    assert response.total == 1
    assert response.instruments[0].symbol == "BTC-USD"
    assert response.instruments[0].venue is None
    assert response.instruments[0].instrument_type == "reference_rate"
    assert response.instruments[0].catalog_source == "yahoo_finance"
    assert response.instruments[0].price_basis == "provider_unspecified"
    assert response.facets.base_assets[0].value == "BTC"
    assert response.facets.quote_assets[0].value == "USD"
    assert response.summary.instrument_count == 2

    with Session(engine) as session:
        eth_response = list_reference_rates(
            ReferenceRateService(SqlAlchemyReferenceRateRepository(session)),
            search="ethereum",
            base_asset="ETH",
            quote_asset="USD",
            status="active",
            offset=0,
            limit=50,
        )
    assert eth_response.total == 1
    assert eth_response.instruments[0].symbol == "ETH-USD"


def test_reference_rate_openapi_contract_is_generated_for_frontend():
    schema = app.openapi()
    operation = schema["paths"]["/reference-rates"]["get"]
    assert operation["operationId"] == "listReferenceRates"
    properties = schema["components"]["schemas"][
        "ReferenceRateInstrumentResponse"
    ]["properties"]
    assert set(properties) == {
        "id", "symbol", "instrument_type", "base_asset", "base_asset_name",
        "quote_asset", "quote_asset_name", "venue", "is_active",
        "catalog_source", "first_session", "last_session", "stored_sessions",
        "price_basis", "price_source", "price_fetched_at",
    }
