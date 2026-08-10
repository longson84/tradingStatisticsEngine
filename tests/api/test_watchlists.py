from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import pytest

from api.db.models import Base, Company, Instrument
from api.main import app
from api.routes.watchlists import refresh_watchlist_prices
from api.repositories.sqlalchemy_watchlist_repository import (
    SqlAlchemyWatchlistRepository,
)
from api.services.watchlist_service import (
    DuplicateWatchlistError,
    InvalidWatchlistCompanyError,
    UnknownWatchlistError,
    WatchlistService,
)
from api.watchlist_refresh_jobs import WatchlistRefreshJob


def _service() -> tuple[WatchlistService, Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add_all([
        Instrument(
            company=Company(display_name="Microsoft", country_code="US", source="test"),
            market="US", ticker="MSFT", currency="USD",
            source="test", is_active=True,
        ),
        Instrument(
            company=Company(display_name="Apple", country_code="US", source="test"),
            market="US", ticker="AAPL", currency="USD",
            source="test", is_active=True,
        ),
        Instrument(
            company=Company(display_name="FPT Corporation", country_code="VN", source="test"),
            market="VN", ticker="FPT", currency="VND",
            source="test", is_active=True,
        ),
    ])
    session.flush()
    return WatchlistService(SqlAlchemyWatchlistRepository(session)), session


def test_watchlist_crud_preserves_order_and_market():
    service, session = _service()
    try:
        created = service.create_watchlist(
            name="  Quality   Growth ",
            market="us",
            description="Candidates",
            tickers=["aapl", "MSFT", "AAPL"],
        )
        assert created.name == "Quality Growth"
        assert created.market == "US"
        assert [row.ticker for row in created.members] == ["AAPL", "MSFT"]

        updated = service.update_watchlist(
            created.id,
            name="Quality Growth",
            description="Updated",
            tickers=["MSFT"],
        )
        assert updated.market == "US"
        assert updated.description == "Updated"
        assert [row.ticker for row in updated.members] == ["MSFT"]
        assert service.list_watchlists("US")[0].member_count == 1

        service.delete_watchlist(created.id)
        with pytest.raises(UnknownWatchlistError):
            service.get_watchlist(created.id)
    finally:
        session.close()


def test_watchlist_rejects_company_from_another_market():
    service, session = _service()
    try:
        with pytest.raises(InvalidWatchlistCompanyError, match="FPT"):
            service.create_watchlist(
                name="US only", market="US", tickers=["MSFT", "FPT"]
            )
    finally:
        session.close()


def test_watchlist_names_are_case_insensitively_unique_per_market():
    service, session = _service()
    try:
        service.create_watchlist(name="Leaders", market="US")
        with pytest.raises(DuplicateWatchlistError):
            service.create_watchlist(name=" leaders ", market="US")
        vn = service.create_watchlist(name="Leaders", market="VN")
        assert vn.market == "VN"
    finally:
        session.close()


def test_openapi_exposes_typed_watchlist_crud():
    paths = app.openapi()["paths"]

    assert paths["/watchlists"]["get"]["operationId"] == "listWatchlists"
    assert paths["/watchlists"]["post"]["operationId"] == "createWatchlist"
    assert paths["/watchlists/{watchlist_id}"]["put"]["operationId"] == "updateWatchlist"
    assert paths["/watchlists/{watchlist_id}"]["delete"]["operationId"] == "deleteWatchlist"
    assert paths["/watchlists/{watchlist_id}/refresh"]["post"]["operationId"] == "refreshWatchlistPrices"
    assert paths["/watchlists/refresh-jobs"]["get"]["operationId"] == "listWatchlistRefreshJobs"
    assert paths["/watchlists/refresh-jobs/{job_id}"]["get"]["operationId"] == "getWatchlistRefreshJob"


def test_refresh_endpoint_starts_job_for_canonical_watchlist(monkeypatch):
    service, session = _service()
    try:
        created = service.create_watchlist(
            name="Leaders", market="US", tickers=["MSFT", "AAPL"]
        )
        calls = []

        def start(watchlist_id, watchlist_name, market):
            calls.append((watchlist_id, watchlist_name, market))
            return WatchlistRefreshJob(
                id="job-1",
                watchlist_id=watchlist_id,
                watchlist_name=watchlist_name,
                market=market,
            )

        monkeypatch.setattr("api.routes.watchlists.start_refresh_job", start)

        response = refresh_watchlist_prices(created.id, service)

        assert calls == [(created.id, "Leaders", "US")]
        assert response.id == "job-1"
        assert response.status == "queued"
    finally:
        session.close()
