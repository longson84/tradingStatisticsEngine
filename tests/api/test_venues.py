from __future__ import annotations

from datetime import time

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from api.db.models import Asset, Base, Instrument, Venue
from api.main import app
from api.repositories.sqlalchemy_venue_repository import SqlAlchemyVenueRepository
from api.routes.venues import list_venues
from api.services.venue_service import VenueService


def _venue_service() -> tuple[VenueService, Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    btc = Asset(
        canonical_code="BTC", name="Bitcoin", asset_type="crypto", source="test"
    )
    usdt = Asset(
        canonical_code="USDT", name="Tether", asset_type="stablecoin", source="test"
    )
    binance = Venue(
        code="BINANCE_SPOT",
        name="Binance Spot",
        venue_type="exchange",
        country_code=None,
        timezone_name="UTC",
        trading_calendar_code="CRYPTO_24_7",
        session_cutoff_time=time(0, 0),
        is_active=True,
        source="test",
    )
    nyse = Venue(
        code="NYSE",
        name="New York Stock Exchange",
        venue_type="stock_exchange",
        country_code="US",
        timezone_name="America/New_York",
        trading_calendar_code="US_EQUITIES",
        session_cutoff_time=time(16, 15),
        is_active=True,
        source="test",
    )
    session.add_all((binance, nyse))
    session.flush()
    session.add_all((
        Instrument(
            venue=binance,
            base_asset=btc,
            quote_asset=usdt,
            settlement_asset=usdt,
            symbol="BTCUSDT",
            instrument_type="spot",
            currency="USDT",
            source="test",
            is_active=True,
        ),
        Instrument(
            venue=binance,
            base_asset=btc,
            quote_asset=usdt,
            settlement_asset=usdt,
            symbol="OLDUSDT",
            instrument_type="spot",
            currency="USDT",
            source="test",
            is_active=False,
        ),
    ))
    session.flush()
    return VenueService(SqlAlchemyVenueRepository(session)), session


def test_venue_catalog_returns_schedule_metadata_and_instrument_counts():
    service, session = _venue_service()
    try:
        response = list_venues(service)
    finally:
        session.close()

    assert response.total == 2
    assert [venue.code for venue in response.venues] == ["BINANCE_SPOT", "NYSE"]
    binance = response.venues[0]
    assert binance.timezone_name == "UTC"
    assert binance.trading_calendar_code == "CRYPTO_24_7"
    assert binance.session_cutoff_time == time(0, 0)
    assert binance.instrument_count == 2
    assert binance.active_instrument_count == 1
    assert response.venues[1].instrument_count == 0


def test_venue_openapi_contract_exposes_calendar_as_venue_metadata():
    schema = app.openapi()
    assert schema["paths"]["/venues"]["get"]["operationId"] == "listVenues"
    properties = schema["components"]["schemas"]["VenueResponse"]["properties"]
    assert {
        "timezone_name",
        "trading_calendar_code",
        "session_cutoff_time",
        "instrument_count",
    }.issubset(properties)
    assert "calendar_id" not in properties
