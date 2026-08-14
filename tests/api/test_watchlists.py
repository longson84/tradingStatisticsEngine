from __future__ import annotations

from datetime import time

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import pytest

from api.db.models import Asset, Base, Company, Instrument, Venue
from api.main import app
from api.repositories.sqlalchemy_watchlist_repository import (
    SqlAlchemyWatchlistRepository,
)
from api.services.watchlist_service import (
    DuplicateWatchlistError,
    InvalidWatchlistInstrumentError,
    UnknownWatchlistError,
    WatchlistService,
)


def _service() -> tuple[WatchlistService, Session, dict[str, int]]:
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
        code="BINANCE", name="Binance", venue_type="exchange", source="test",
        timezone_name="UTC", trading_calendar_code="CRYPTO_24_7",
        session_cutoff_time=time(0, 0),
    )
    nasdaq = Venue(
        code="NASDAQ", name="Nasdaq", venue_type="exchange", source="test",
        country_code="US", timezone_name="America/New_York",
        trading_calendar_code="US_EQUITIES", session_cutoff_time=time(16, 15),
    )
    hose = Venue(
        code="HOSE", name="HOSE", venue_type="exchange", source="test",
        country_code="VN", timezone_name="Asia/Ho_Chi_Minh",
        trading_calendar_code="VN_EQUITIES", session_cutoff_time=time(15, 15),
    )
    instruments = {
        "MSFT": Instrument(
            venue=nasdaq,
            company=Company(
                display_name="Microsoft",
                domicile_country_code="US",
                source="test",
            ),
            symbol="MSFT", instrument_type="common_stock",
            currency="USD", source="test", is_active=True,
        ),
        "AAPL": Instrument(
            venue=nasdaq,
            company=Company(
                display_name="Apple",
                domicile_country_code="US",
                source="test",
            ),
            symbol="AAPL", instrument_type="common_stock",
            currency="USD", source="test", is_active=True,
        ),
        "FPT": Instrument(
            venue=hose,
            company=Company(
                display_name="FPT Corporation",
                domicile_country_code="VN",
                source="test",
            ),
            symbol="FPT", instrument_type="common_stock",
            currency="VND", source="test", is_active=True,
        ),
        "BTCUSDT": Instrument(
            venue=binance,
            base_asset=btc,
            quote_asset=usdt,
            settlement_asset=usdt,
            symbol="BTCUSDT", instrument_type="spot",
            currency="USDT", source="test", is_active=True,
        ),
        "SPX": Instrument(
            symbol="SPX", instrument_type="market_index",
            currency="USD", source="test", is_active=True,
        ),
    }
    session.add_all(instruments.values())
    session.flush()
    ids = {symbol: instrument.id for symbol, instrument in instruments.items()}
    return WatchlistService(SqlAlchemyWatchlistRepository(session)), session, ids


def test_watchlist_crud_preserves_exact_instrument_order_across_markets():
    service, session, ids = _service()
    try:
        created = service.create_watchlist(
            name="  Multi   Asset ",
            description="Candidates",
            instrument_ids=[
                ids["BTCUSDT"], ids["MSFT"], ids["SPX"],
                ids["BTCUSDT"], ids["FPT"],
            ],
        )
        assert created.name == "Multi Asset"
        assert created.instrument_types == ("common_stock", "market_index", "spot")
        assert [row.instrument_id for row in created.members] == [
            ids["BTCUSDT"], ids["MSFT"], ids["SPX"], ids["FPT"]
        ]
        assert created.members[0].company_name is None
        assert created.members[0].venue_code == "BINANCE"
        assert created.market_index_count == 1
        assert created.members[2].venue_code is None

        updated = service.update_watchlist(
            created.id,
            name="Multi Asset",
            description="Updated",
            instrument_ids=[ids["MSFT"]],
        )
        assert updated.description == "Updated"
        assert [row.symbol for row in updated.members] == ["MSFT"]
        assert service.list_watchlists()[0].member_count == 1

        service.delete_watchlist(created.id)
        with pytest.raises(UnknownWatchlistError):
            service.get_watchlist(created.id)
    finally:
        session.close()


def test_watchlist_rejects_unknown_instrument_id():
    service, session, ids = _service()
    try:
        with pytest.raises(InvalidWatchlistInstrumentError, match="999999"):
            service.create_watchlist(
                name="Invalid", instrument_ids=[ids["MSFT"], 999999]
            )
    finally:
        session.close()


def test_watchlist_names_are_globally_case_insensitively_unique():
    service, session, _ = _service()
    try:
        service.create_watchlist(name="Leaders")
        with pytest.raises(DuplicateWatchlistError):
            service.create_watchlist(name=" leaders ")
    finally:
        session.close()


def test_openapi_exposes_instrument_id_watchlist_contract():
    schema = app.openapi()
    paths = schema["paths"]

    assert paths["/watchlists"]["get"]["operationId"] == "listWatchlists"
    assert paths["/watchlists"]["post"]["operationId"] == "createWatchlist"
    assert paths["/watchlists/{watchlist_id}"]["put"]["operationId"] == "updateWatchlist"
    assert paths["/watchlists/{watchlist_id}"]["delete"]["operationId"] == "deleteWatchlist"
    assert "/watchlists/{watchlist_id}/refresh" not in paths
    assert "/watchlists/refresh-jobs" not in paths
    request = schema["components"]["schemas"]["WatchlistCreateRequest"]
    assert "instrument_ids" in request["properties"]
    assert "market" not in request["properties"]
    assert "tickers" not in request["properties"]
    summary = schema["components"]["schemas"]["WatchlistSummaryResponse"]
    assert "market_index_count" in summary["properties"]
