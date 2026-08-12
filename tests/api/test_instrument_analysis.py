from __future__ import annotations

from datetime import UTC, date, datetime, time

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from api.db.company_import import import_company_universes
from api.db.models import Asset, Base, Instrument, PriceBar, PriceBarCoverage, Venue
from api.main import app
from api.repositories.sqlalchemy_instrument_analysis_repository import (
    SqlAlchemyInstrumentAnalysisRepository,
)
from api.repositories.sqlalchemy_instrument_routing_repository import (
    SqlAlchemyInstrumentRoutingRepository,
)
from api.routes.instruments import list_analysis_instruments
from api.services.company_price_service import CompanyPriceUnavailableError
from api.services.instrument_analysis_service import InstrumentAnalysisService
from api.services.instrument_analysis_service import InstrumentPriceUnavailableError


def _service_with_msft_history():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    import_company_universes(engine)
    session = Session(engine)
    instrument = session.scalar(select(Instrument).where(
        Instrument.ticker == "MSFT",
    ))
    assert instrument is not None
    fetched_at = datetime(2026, 8, 10, tzinfo=UTC)
    session.add(PriceBarCoverage(
        instrument_id=instrument.id,
        price_basis="adjusted",
        first_date=date(2026, 8, 7),
        last_date=date(2026, 8, 7),
        row_count=1,
        source="yfinance",
        fetched_at=fetched_at,
    ))
    session.add(PriceBar(
        instrument_id=instrument.id,
        trading_date=date(2026, 8, 7),
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.5,
        volume=1_000_000.0,
        currency="USD",
        price_scale=1,
        price_basis="adjusted",
        source="yfinance",
        fetched_at=fetched_at,
    ))
    session.flush()
    return (
        InstrumentAnalysisService(
            SqlAlchemyInstrumentAnalysisRepository(session),
            SqlAlchemyInstrumentRoutingRepository(session),
        ),
        session,
        instrument.id,
    )


def test_analysis_instrument_search_returns_stable_id_and_issuer_metadata():
    service, session, instrument_id = _service_with_msft_history()
    try:
        response = list_analysis_instruments(
            service,
            scope="equity",
            universe=None,
            search="Microsoft",
            has_price_history=True,
            offset=0,
            limit=20,
        )
    finally:
        session.close()

    assert response.total == 1
    row = response.instruments[0]
    assert row.id == instrument_id
    assert row.symbol == "MSFT"
    assert row.company_name == "Microsoft Corporation"
    assert row.instrument_type == "common_stock"
    assert row.price_basis == "adjusted"
    assert row.stored_sessions == 1


def test_instrument_price_history_is_read_by_exact_instrument_id():
    service, session, instrument_id = _service_with_msft_history()
    try:
        result = service.get_current_history(
            instrument_id,
            now=datetime(2026, 8, 10, 12, tzinfo=UTC),
        )
    finally:
        session.close()

    assert result.instrument.id == instrument_id
    assert result.instrument.symbol == "MSFT"
    assert result.prices.symbol == "MSFT"
    assert result.prices.data.index[-1].date() == date(2026, 8, 7)
    assert result.price_basis == "adjusted"


def test_equity_refresh_failure_remains_an_analysis_price_error():
    _, session, instrument_id = _service_with_msft_history()

    class MissingPrices:
        def get_current_instrument_history(self, instrument_id, *, now):
            raise CompanyPriceUnavailableError("No stored price history")

    service = InstrumentAnalysisService(
        SqlAlchemyInstrumentAnalysisRepository(session),
        SqlAlchemyInstrumentRoutingRepository(session),
        MissingPrices(),
    )
    try:
        try:
            service.get_current_history(instrument_id)
        except InstrumentPriceUnavailableError as exc:
            assert str(exc) == "No stored price history"
        else:
            raise AssertionError("Expected InstrumentPriceUnavailableError")
    finally:
        session.close()


def test_instrument_openapi_and_rarity_contracts_use_instrument_identity():
    schema = app.openapi()

    operation = schema["paths"]["/instruments"]["get"]
    assert operation["operationId"] == "listAnalysisInstruments"
    request = schema["components"]["schemas"]["RarityRequest"]["properties"]
    assert "instrument_id" in request
    assert "market" not in request
    assert "ticker" not in request
    response = schema["components"]["schemas"]["RarityAnalysisResponse"][
        "properties"
    ]
    assert {
        "instrument_id", "instrument_type", "company_name", "venue_code",
        "base_asset", "quote_asset", "currency",
    }.issubset(response)


def test_crypto_scopes_and_exact_id_keep_venues_and_reference_rates_distinct():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    btc = Asset(
        canonical_code="BTC", name="Bitcoin", asset_type="crypto",
        is_active=True, source="test",
    )
    usdt = Asset(
        canonical_code="USDT", name="Tether", asset_type="stablecoin",
        is_active=True, source="test",
    )
    usd = Asset(
        canonical_code="USD", name="United States Dollar", asset_type="fiat",
        is_active=True, source="test",
    )
    binance = Venue(
        code="BINANCE_SPOT", name="Binance Spot", venue_type="exchange",
        is_active=True, source="test", timezone_name="UTC",
        trading_calendar_code="CRYPTO_24_7", session_cutoff_time=time(0, 0),
    )
    okx = Venue(
        code="OKX_SPOT", name="OKX Spot", venue_type="exchange",
        is_active=True, source="test", timezone_name="UTC",
        trading_calendar_code="CRYPTO_24_7", session_cutoff_time=time(0, 0),
    )
    session.add_all((btc, usdt, usd, binance, okx))
    session.flush()
    instruments = (
        Instrument(
            venue_id=binance.id, base_asset_id=btc.id, quote_asset_id=usdt.id,
            settlement_asset_id=usdt.id, ticker="BTCUSDT",
            instrument_type="spot", currency="USDT", is_active=True,
            source="test",
        ),
        Instrument(
            venue_id=okx.id, base_asset_id=btc.id, quote_asset_id=usdt.id,
            settlement_asset_id=usdt.id, ticker="BTCUSDT",
            instrument_type="spot", currency="USDT", is_active=True,
            source="test",
        ),
        Instrument(
            base_asset_id=btc.id, quote_asset_id=usd.id,
            settlement_asset_id=usd.id, ticker="BTC-USD",
            instrument_type="reference_rate", currency="USD", is_active=True,
            source="test",
        ),
    )
    session.add_all(instruments)
    session.flush()
    fetched_at = datetime(2026, 8, 10, tzinfo=UTC)
    for instrument, basis, source, close in (
        (instruments[0], "venue_unadjusted", "binance", 100.0),
        (instruments[1], "venue_unadjusted", "okx", 101.0),
        (instruments[2], "provider_unspecified", "yahoo_finance", 102.0),
    ):
        session.add(PriceBarCoverage(
            instrument_id=instrument.id,
            price_basis=basis,
            first_date=date(2026, 8, 9),
            last_date=date(2026, 8, 9),
            row_count=1,
            source=source,
            fetched_at=fetched_at,
        ))
        session.add(PriceBar(
            instrument_id=instrument.id,
            trading_date=date(2026, 8, 9),
            open=close,
            high=close,
            low=close,
            close=close,
            volume=None,
            currency=instrument.currency,
            price_scale=1,
            price_basis=basis,
            source=source,
            fetched_at=fetched_at,
        ))
    session.flush()
    service = InstrumentAnalysisService(
        SqlAlchemyInstrumentAnalysisRepository(session),
        SqlAlchemyInstrumentRoutingRepository(session),
    )
    try:
        spots = service.list_instruments(scope="crypto_spot", search="BTCUSDT")
        rates = service.list_instruments(scope="reference_rate", search="BTC")
        okx_history = service.get_current_history(
            instruments[1].id,
            now=datetime(2026, 8, 10, 12, tzinfo=UTC),
        )
        stored_set = service.get_stored_histories(
            [instruments[1].id, instruments[2].id],
            now=datetime(2026, 8, 10, 12, tzinfo=UTC),
        )
    finally:
        session.close()

    assert spots.total == 2
    assert {row.venue_code for row in spots.rows} == {"BINANCE_SPOT", "OKX_SPOT"}
    assert rates.total == 1
    assert rates.rows[0].venue_code is None
    assert rates.rows[0].symbol == "BTC-USD"
    assert okx_history.instrument.venue_code == "OKX_SPOT"
    assert okx_history.prices.data["close"].iloc[-1] == 101.0
    assert okx_history.price_source == "okx"
    assert stored_set.prices[instruments[1].id].data["close"].iloc[-1] == 101.0
    assert stored_set.prices[instruments[2].id].data["close"].iloc[-1] == 102.0
    assert stored_set.price_sources == {
        instruments[1].id: "okx",
        instruments[2].id: "yahoo_finance",
    }
    assert stored_set.missing_instrument_ids == ()
