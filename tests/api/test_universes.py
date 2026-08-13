from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from api.db.models import (
    Asset,
    Base,
    Company,
    Instrument,
    Universe,
    UniverseMembership,
    UniverseSyncRun,
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
from api.routes.universes import list_universe_sync_runs, list_universes
from api.services.instrument_analysis_service import InstrumentAnalysisService
from api.services.universe_service import UniverseService


def _services():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    fetched_at = datetime(2026, 8, 10, tzinfo=UTC)
    msft = Instrument(
        company=Company(display_name="Microsoft", country_code="US", source="test"),
        symbol="MSFT",
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
        symbol="BTCUSDT",
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
        symbol="OLDUSDT",
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
    session.add_all((
        UniverseSyncRun(
            universe_code="US500",
            source="index_feed",
            status="succeeded",
            started_at=fetched_at - timedelta(minutes=2),
            finished_at=fetched_at - timedelta(minutes=1),
            effective_date=date(2026, 8, 8),
            received_count=503,
            added_count=2,
            removed_count=1,
            unchanged_count=501,
        ),
        UniverseSyncRun(
            universe_code="US500",
            source="index_feed",
            status="failed",
            started_at=fetched_at,
            finished_at=fetched_at + timedelta(seconds=5),
            received_count=0,
            added_count=0,
            removed_count=0,
            unchanged_count=0,
            error="provider offline",
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


def test_universe_sync_history_is_paginated_newest_first():
    universe_service, _, session, _ = _services()
    us500 = next(
        row for row in universe_service.list_universes() if row.code == "US500"
    )
    try:
        first_page = list_universe_sync_runs(
            us500.id,
            universe_service,
            offset=0,
            limit=1,
        )
        second_page = list_universe_sync_runs(
            us500.id,
            universe_service,
            offset=1,
            limit=1,
        )
    finally:
        session.close()

    assert first_page.total == 2
    assert first_page.universe_code == "US500"
    assert first_page.runs[0].status == "failed"
    assert first_page.runs[0].error == "provider offline"
    assert second_page.runs[0].status == "succeeded"
    assert second_page.runs[0].effective_date == date(2026, 8, 8)
    assert second_page.runs[0].received_count == 503


def test_universe_openapi_contract_is_canonical_and_not_company_scoped():
    schema = app.openapi()
    assert schema["paths"]["/universes"]["get"]["operationId"] == "listUniverses"
    assert (
        schema["paths"]["/universes/{universe_id}/sync-runs"]["get"]["operationId"]
        == "listUniverseSyncRuns"
    )
    instrument_query = schema["paths"]["/instruments"]["get"]["parameters"]
    assert "universe" in {parameter["name"] for parameter in instrument_query}
    properties = schema["components"]["schemas"]["UniverseCatalogResponse"][
        "properties"
    ]
    assert {"instrument_count", "active_instrument_count", "source"}.issubset(
        properties
    )
    assert "market" not in properties
    run_properties = schema["components"]["schemas"]["UniverseSyncRunResponse"][
        "properties"
    ]
    assert {
        "status", "source", "started_at", "finished_at", "effective_date",
        "received_count", "added_count", "removed_count", "unchanged_count",
        "error",
    }.issubset(run_properties)
