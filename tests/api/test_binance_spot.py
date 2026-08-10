from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
import hashlib
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import httpx
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from api.db.models import (
    Asset,
    Base,
    Company,
    Instrument,
    PriceBar,
    PriceBarCoverage,
    Universe,
    UniverseMembership,
    Venue,
)
from api.providers.binance_spot import (
    BinanceDailyKline,
    BinancePublicDataClient,
    BinanceSpotCatalog,
    BinanceSpotClient,
    BinanceSpotSymbol,
)
from api.repositories.sqlalchemy_crypto_market_repository import (
    SqlAlchemyCryptoMarketRepository,
)
from api.repositories.sqlalchemy_company_repository import SqlAlchemyCompanyRepository
from api.repositories.sqlalchemy_price_bar_repository import (
    SqlAlchemyPriceBarRepository,
)
from api.services.binance_spot_service import BinanceSpotService
from api.services.crypto_instrument_service import CryptoInstrumentService
from api.routes.crypto import list_crypto_markets
from api.main import app


def _symbol(
    symbol: str,
    base: str,
    quote: str,
    *,
    status: str = "TRADING",
) -> BinanceSpotSymbol:
    return BinanceSpotSymbol(
        symbol=symbol,
        status=status,
        base_asset=base,
        quote_asset=quote,
        base_precision=8,
        quote_precision=8,
        price_tick_size=Decimal("0.01"),
        quantity_step_size=Decimal("0.00001"),
        minimum_quantity=Decimal("0.00001"),
        minimum_notional=Decimal("5"),
        is_spot_trading_allowed=True,
    )


def _catalog(*symbols: BinanceSpotSymbol) -> BinanceSpotCatalog:
    return BinanceSpotCatalog(
        symbols=symbols,
        fetched_at=datetime(2026, 8, 9, 12, tzinfo=UTC),
    )


def test_public_rest_client_parses_catalog_and_daily_klines():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("exchangeInfo"):
            return httpx.Response(200, json={"symbols": [{
                "symbol": "BTCUSDT",
                "status": "TRADING",
                "baseAsset": "BTC",
                "baseAssetPrecision": 8,
                "quoteAsset": "USDT",
                "quoteAssetPrecision": 8,
                "isSpotTradingAllowed": True,
                "filters": [
                    {"filterType": "PRICE_FILTER", "tickSize": "0.01000000"},
                    {
                        "filterType": "LOT_SIZE",
                        "minQty": "0.00001000",
                        "stepSize": "0.00001000",
                    },
                    {"filterType": "NOTIONAL", "minNotional": "5.00000000"},
                ],
            }]})
        if request.url.path.endswith("klines"):
            return httpx.Response(200, json=[[
                1786233600000,
                "100.0",
                "105.0",
                "99.0",
                "103.0",
                "12.5",
                1786319999999,
            ]])
        return httpx.Response(404)

    http = httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://example.test"
    )
    client = BinanceSpotClient(client=http)
    catalog = client.fetch_catalog()
    assert catalog.symbols[0].symbol == "BTCUSDT"
    assert catalog.symbols[0].minimum_notional == Decimal("5.00000000")

    rows = client.fetch_daily_klines(
        "BTCUSDT", date(2026, 8, 9), date(2026, 8, 9)
    )
    assert len(rows) == 1
    assert rows[0].trading_date == date(2026, 8, 9)
    assert rows[0].source == "binance_spot_rest"


def test_public_archive_client_verifies_checksum_and_microsecond_timestamps():
    csv_row = (
        "1735689600000000,4.15,4.20,4.10,4.18,100," 
        "1735775999999999,0,0,0,0,0\n"
    )
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr("BTCUSDT-1d-2025-01.csv", csv_row)
    payload = buffer.getvalue()
    checksum = hashlib.sha256(payload).hexdigest()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith(".CHECKSUM"):
            return httpx.Response(200, text=f"{checksum}  file.zip\n")
        return httpx.Response(200, content=payload)

    http = httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://example.test"
    )
    result = BinancePublicDataClient(client=http).fetch_month(
        "BTCUSDT", date(2025, 1, 1)
    )
    assert result.found is True
    assert result.klines[0].trading_date == date(2025, 1, 1)
    assert result.klines[0].source == "binance_public_data"


def test_catalog_sync_creates_assets_venue_spot_instruments_and_active_universe():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session, session.begin():
        result = BinanceSpotService(
            SqlAlchemyCryptoMarketRepository(session)
        ).sync_catalog(_catalog(
            _symbol("BTCUSDT", "BTC", "USDT"),
            _symbol("ETHUSDT", "ETH", "USDT", status="BREAK"),
        ))
        assert result.received_instruments == 2
        assert result.active_instruments == 1
        assert result.added_assets == 3

    with Session(engine) as session:
        assert session.scalar(select(func.count(Company.id))) == 0
        assert session.scalar(select(func.count(Asset.id))) == 3
        usdt = session.scalar(select(Asset).where(Asset.canonical_code == "USDT"))
        assert usdt is not None and usdt.asset_type == "stablecoin"
        venue = session.scalar(select(Venue).where(Venue.code == "BINANCE_SPOT"))
        assert venue is not None
        btc = session.scalar(select(Instrument).where(Instrument.ticker == "BTCUSDT"))
        assert btc is not None
        assert btc.company_id is None
        assert btc.instrument_type == "spot"
        assert btc.base_asset is not None and btc.base_asset.canonical_code == "BTC"
        assert btc.quote_asset is not None and btc.quote_asset.canonical_code == "USDT"
        universe = session.scalar(select(Universe).where(Universe.code == "BINANCE_SPOT"))
        assert universe is not None and universe.market == "CRYPTO"
        assert SqlAlchemyCompanyRepository(session).list_universes() == ()
        members = session.scalars(
            select(Instrument)
            .join(UniverseMembership)
            .where(UniverseMembership.universe_id == universe.id)
        ).all()
        assert [row.ticker for row in members] == ["BTCUSDT"]


def test_catalog_resync_deactivates_missing_market_without_deleting_history():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session, session.begin():
        service = BinanceSpotService(SqlAlchemyCryptoMarketRepository(session))
        service.sync_catalog(_catalog(
            _symbol("BTCUSDT", "BTC", "USDT"),
            _symbol("ETHUSDT", "ETH", "USDT"),
        ))
    with Session(engine) as session, session.begin():
        result = BinanceSpotService(
            SqlAlchemyCryptoMarketRepository(session)
        ).sync_catalog(_catalog(_symbol("BTCUSDT", "BTC", "USDT")))
        assert result.deactivated_instruments == 1
    with Session(engine) as session:
        eth = session.scalar(select(Instrument).where(Instrument.ticker == "ETHUSDT"))
        assert eth is not None and eth.is_active is False


def test_store_history_writes_quote_asset_and_venue_specific_provenance():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session, session.begin():
        BinanceSpotService(
            SqlAlchemyCryptoMarketRepository(session)
        ).sync_catalog(_catalog(_symbol("BTCUSDT", "BTC", "USDT")))
    with Session(engine) as session:
        instrument = BinanceSpotService(
            SqlAlchemyCryptoMarketRepository(session)
        ).list_instruments(symbols=("BTCUSDT",))[0]
    kline = BinanceDailyKline(
        symbol="BTCUSDT",
        trading_date=date(2026, 8, 8),
        open=Decimal("100"),
        high=Decimal("110"),
        low=Decimal("90"),
        close=Decimal("105"),
        volume=Decimal("123.45"),
        open_time=datetime(2026, 8, 8, tzinfo=UTC),
        close_time=datetime(2026, 8, 8, 23, 59, 59, tzinfo=UTC),
        source="binance_public_data",
    )
    with Session(engine) as session, session.begin():
        result = BinanceSpotService(
            SqlAlchemyCryptoMarketRepository(session),
            SqlAlchemyPriceBarRepository(session),
        ).store_history(
            instrument,
            (kline,),
            fetched_at=datetime(2026, 8, 9, tzinfo=UTC),
        )
        assert result.stored_rows == 1
    with Session(engine) as session:
        bar = session.scalar(select(PriceBar))
        assert bar is not None
        assert bar.currency == "USDT"
        assert bar.price_basis == "venue_unadjusted"
        assert bar.source == "binance_public_data"


def test_crypto_market_route_paginates_filters_and_preserves_decimal_rules():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session, session.begin():
        BinanceSpotService(
            SqlAlchemyCryptoMarketRepository(session)
        ).sync_catalog(_catalog(
            _symbol("BTCUSDT", "BTC", "USDT"),
            _symbol("ETHUSDT", "ETH", "USDT"),
            _symbol("ETHBTC", "ETH", "BTC", status="BREAK"),
        ))
    with Session(engine) as session, session.begin():
        venue = Venue(
            code="OKX_SPOT",
            name="OKX Spot",
            venue_type="exchange",
            is_active=True,
            source="test",
        )
        session.add(venue)
        session.flush()
        btc_asset = session.scalar(
            select(Asset).where(Asset.canonical_code == "BTC")
        )
        usdt_asset = session.scalar(
            select(Asset).where(Asset.canonical_code == "USDT")
        )
        assert btc_asset is not None and usdt_asset is not None
        session.add(Instrument(
            venue_id=venue.id,
            base_asset_id=btc_asset.id,
            quote_asset_id=usdt_asset.id,
            settlement_asset_id=usdt_asset.id,
            market="CRYPTO",
            ticker="BTC-USDT",
            instrument_type="spot",
            exchange="OKX",
            currency="USDT",
            price_tick_size=Decimal("0.1"),
            quantity_step_size=Decimal("0.00001"),
            minimum_quantity=Decimal("0.00001"),
            minimum_notional=Decimal("5"),
            is_active=True,
            source="test",
        ))
        btc = session.scalar(
            select(Instrument).where(Instrument.ticker == "BTCUSDT")
        )
        assert btc is not None
        session.add(PriceBarCoverage(
            instrument_id=btc.id,
            price_basis="venue_unadjusted",
            first_date=date(2025, 1, 1),
            last_date=date(2025, 1, 31),
            row_count=31,
            source="binance_public_data",
            fetched_at=datetime(2026, 8, 9, tzinfo=UTC),
        ))
    with Session(engine) as session:
        service = CryptoInstrumentService(
            SqlAlchemyCryptoMarketRepository(session)
        )
        response = list_crypto_markets(
            service,
            venue_code="BINANCE_SPOT",
            search=None,
            quote_asset="USDT",
            status="active",
            offset=0,
            limit=1,
        )
        all_venues = list_crypto_markets(
            service,
            venue_code=None,
            search=None,
            quote_asset="USDT",
            status="active",
            offset=0,
            limit=10,
        )

    assert response.total == 2
    assert len(response.instruments) == 1
    assert response.instruments[0].symbol == "BTCUSDT"
    assert response.instruments[0].venue_code == "BINANCE_SPOT"
    assert response.instruments[0].venue_name == "Binance Spot"
    assert response.instruments[0].price_tick_size == "0.01"
    assert response.instruments[0].stored_sessions == 31
    assert response.facets.active_count == 2
    assert response.facets.inactive_count == 0
    assert {row.value: row.count for row in response.facets.quote_assets} == {
        "USDT": 2,
    }
    assert response.summary.instrument_count == 3
    assert response.summary.active_count == 2
    assert response.summary.inactive_count == 1
    assert response.summary.with_history_count == 1
    assert all_venues.total == 3
    assert {row.code: row.count for row in all_venues.facets.venues} == {
        "BINANCE_SPOT": 2,
        "OKX_SPOT": 1,
    }


def test_crypto_market_openapi_contract_is_generated_for_frontend():
    schema = app.openapi()

    operation = schema["paths"]["/crypto/markets"]["get"]
    assert operation["operationId"] == "listCryptoMarkets"
    properties = schema["components"]["schemas"][
        "CryptoMarketInstrumentResponse"
    ]["properties"]
    assert set(properties) == {
        "id", "venue_code", "venue_name", "symbol", "base_asset",
        "quote_asset", "is_active",
        "price_tick_size", "quantity_step_size", "minimum_quantity",
        "minimum_notional", "first_session", "last_session",
        "stored_sessions", "price_source",
    }
