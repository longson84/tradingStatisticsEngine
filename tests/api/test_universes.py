from __future__ import annotations

from datetime import UTC, datetime, time

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from api.db.models import (
    Asset,
    Base,
    Company,
    Instrument,
    Universe,
    UniverseMembership,
    Venue,
)
from api.main import app
from api.repositories.sqlalchemy_instrument_analysis_repository import (
    SqlAlchemyInstrumentAnalysisRepository,
)
from api.repositories.sqlalchemy_instrument_routing_repository import (
    SqlAlchemyInstrumentRoutingRepository,
)
from api.repositories.sqlalchemy_universe_repository import (
    SqlAlchemyUniverseRepository,
)
from api.routes.universes import list_universes
from api.services.instrument_analysis_service import InstrumentAnalysisService
from api.services.universe_service import UniverseService


def _services():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    fetched_at = datetime(2026, 8, 10, tzinfo=UTC)
    msft = Instrument(
        company=Company(display_name="Microsoft", country_code="US", source="test"),
        ticker="MSFT",
        instrument_type="common_stock",
        currency="USD",
        source="test",
        is_active=True,
    )
    btc = Asset(
        canonical_code="BTC", name="Bitcoin", asset_type="crypto", source="test"
    )
    usdt = Asset(
        canonical_code="USDT", name="Tether", asset_type="stablecoin", source="test"
    )
    binance = Venue(
        code="BINANCE_SPOT", name="Binance Spot", venue_type="exchange", source="test",
        timezone_name="UTC", trading_calendar_code="CRYPTO_24_7",
        session_cutoff_time=time(0, 0),
    )
    btcusdt = Instrument(
        venue=binance,
        base_asset=btc,
        quote_asset=usdt,
        settlement_asset=usdt,
        ticker="BTCUSDT",
        instrument_type="spot",
        currency="USDT",
        source="test",
        is_active=True,
    )
    retired = Instrument(
        venue=binance,
        base_asset=btc,
        quote_asset=usdt,
        settlement_asset=usdt,
        ticker="OLDUSDT",
        instrument_type="spot",
        currency="USDT",
        source="test",
        is_active=False,
    )
    us500 = Universe(
        code="US500", name="S&P 500", description="US index",
        as_of="2026-08-08", fetched_at=fetched_at, source="index_feed",
    )
    binance_spot = Universe(
        code="BINANCE_SPOT", name="Binance Spot",
        description="Active Binance Spot instruments", as_of="2026-08-10",
        fetched_at=fetched_at, source="binance_spot_exchange_info",
    )
    session.add_all((msft, btcusdt, retired, us500, binance_spot))
    session.flush()
    session.add_all((
        UniverseMembership(
            universe_id=us500.id, instrument_id=msft.id,
            source="index_feed", fetched_at=fetched_at,
        ),
        UniverseMembership(
            universe_id=binance_spot.id, instrument_id=btcusdt.id,
            source="binance_spot_exchange_info", fetched_at=fetched_at,
        ),
        UniverseMembership(
            universe_id=binance_spot.id, instrument_id=retired.id,
            source="binance_spot_exchange_info", fetched_at=fetched_at,
        ),
    ))
    session.flush()
    return (
        UniverseService(SqlAlchemyUniverseRepository(session)),
        InstrumentAnalysisService(
            SqlAlchemyInstrumentAnalysisRepository(session),
            SqlAlchemyInstrumentRoutingRepository(session),
        ),
        session,
        btcusdt.id,
    )


def test_universe_catalog_includes_equity_and_crypto_collections():
    universe_service, _, session, _ = _services()
    try:
        response = list_universes(universe_service)
    finally:
        session.close()

    assert [row.code for row in response.universes] == ["BINANCE_SPOT", "US500"]
    crypto = response.universes[0]
    assert crypto.instrument_count == 2
    assert crypto.active_instrument_count == 1
    assert crypto.instrument_types == ["spot"]
    assert crypto.venue_codes == ["BINANCE_SPOT"]


def test_universe_membership_filters_the_canonical_instrument_catalog():
    _, instrument_service, session, btcusdt_id = _services()
    try:
        result = instrument_service.list_instruments(
            universe="BINANCE_SPOT",
            has_price_history=False,
            limit=50,
        )
    finally:
        session.close()

    assert result.total == 1
    assert result.rows[0].id == btcusdt_id
    assert result.rows[0].symbol == "BTCUSDT"


def test_universe_openapi_contract_is_canonical_and_not_company_scoped():
    schema = app.openapi()
    assert schema["paths"]["/universes"]["get"]["operationId"] == "listUniverses"
    instrument_query = schema["paths"]["/instruments"]["get"]["parameters"]
    assert "universe" in {parameter["name"] for parameter in instrument_query}
    properties = schema["components"]["schemas"]["UniverseCatalogResponse"][
        "properties"
    ]
    assert {"instrument_count", "active_instrument_count", "source"}.issubset(
        properties
    )
    assert "market" not in properties
