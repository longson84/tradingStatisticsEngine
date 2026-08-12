from __future__ import annotations

from datetime import time

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import pytest

from api.db.models import Asset, Base, Company, Instrument, Venue
from api.main import app
from api.routes.watchlists import refresh_watchlist_prices
from api.repositories.sqlalchemy_watchlist_repository import (
    SqlAlchemyWatchlistRepository,
)
from api.services.watchlist_service import (
    DuplicateWatchlistError,
    InvalidWatchlistInstrumentError,
    UnknownWatchlistError,
    WatchlistService,
)
from api.watchlist_refresh_jobs import WatchlistRefreshJob


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
            company=Company(display_name="Microsoft", country_code="US", source="test"),
            ticker="MSFT", instrument_type="common_stock",
            currency="USD", source="test", is_active=True,
        ),
        "AAPL": Instrument(
            venue=nasdaq,
            company=Company(display_name="Apple", country_code="US", source="test"),
            ticker="AAPL", instrument_type="common_stock",
            currency="USD", source="test", is_active=True,
        ),
        "FPT": Instrument(
            venue=hose,
            company=Company(
                display_name="FPT Corporation", country_code="VN", source="test"
            ),
            ticker="FPT", instrument_type="common_stock",
            currency="VND", source="test", is_active=True,
        ),
        "BTCUSDT": Instrument(
            venue=binance,
            base_asset=btc,
            quote_asset=usdt,
            settlement_asset=usdt,
            ticker="BTCUSDT", instrument_type="spot",
            currency="USDT", source="test", is_active=True,
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
            instrument_ids=[ids["BTCUSDT"], ids["MSFT"], ids["BTCUSDT"], ids["FPT"]],
        )
        assert created.name == "Multi Asset"
        assert created.instrument_types == ("common_stock", "spot")
        assert [row.instrument_id for row in created.members] == [
            ids["BTCUSDT"], ids["MSFT"], ids["FPT"]
        ]
        assert created.members[0].company_name is None
        assert created.members[0].venue_code == "BINANCE"
        assert created.equity_refresh_adapter is None

        updated = service.update_watchlist(
            created.id,
            name="Multi Asset",
            description="Updated",
            instrument_ids=[ids["MSFT"]],
        )
        assert updated.description == "Updated"
        assert [row.symbol for row in updated.members] == ["MSFT"]
        assert updated.equity_refresh_adapter == "yfinance"
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
    assert paths["/watchlists/{watchlist_id}/refresh"]["post"]["operationId"] == "refreshWatchlistPrices"
    assert paths["/watchlists/refresh-jobs"]["get"]["operationId"] == "listWatchlistRefreshJobs"
    request = schema["components"]["schemas"]["WatchlistCreateRequest"]
    assert "instrument_ids" in request["properties"]
    assert "market" not in request["properties"]
    assert "tickers" not in request["properties"]


def test_refresh_endpoint_starts_job_for_homogeneous_equity_watchlist(monkeypatch):
    service, session, ids = _service()
    try:
        created = service.create_watchlist(
            name="Leaders", instrument_ids=[ids["MSFT"], ids["AAPL"]]
        )
        calls = []

        def start(watchlist_id, watchlist_name, routing_adapter):
            calls.append((watchlist_id, watchlist_name, routing_adapter))
            return WatchlistRefreshJob(
                id="job-1",
                watchlist_id=watchlist_id,
                watchlist_name=watchlist_name,
                routing_adapter=routing_adapter,
            )

        monkeypatch.setattr("api.routes.watchlists.start_refresh_job", start)

        response = refresh_watchlist_prices(created.id, service)

        assert calls == [(created.id, "Leaders", "yfinance")]
        assert response.id == "job-1"
        assert response.status == "queued"
    finally:
        session.close()


def test_refresh_endpoint_rejects_mixed_instrument_watchlist():
    service, session, ids = _service()
    try:
        created = service.create_watchlist(
            name="Mixed", instrument_ids=[ids["MSFT"], ids["BTCUSDT"]]
        )
        with pytest.raises(HTTPException) as exc_info:
            refresh_watchlist_prices(created.id, service)
        assert exc_info.value.status_code == 422
        assert "only US equities or only VN equities" in exc_info.value.detail
    finally:
        session.close()
