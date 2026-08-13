"""Refresh canonical price history for one exact instrument ID."""
from __future__ import annotations

import argparse
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.orm import Session

from api.db.session import create_db_engine, session_scope
from api.instrument_data_routing import (
    InstrumentDataRoute,
    resolve_instrument_data_route,
)
from api.market_sessions import latest_completed_venue_session
from api.providers.binance_spot import (
    BinancePublicDataClient,
    BinanceSpotClient,
    BinanceSpotHistoryLoader,
)
from api.providers.vietnam_price_loader import VietnamPriceLoader
from api.repositories.sqlalchemy_crypto_market_repository import (
    SqlAlchemyCryptoMarketRepository,
)
from api.repositories.sqlalchemy_instrument_analysis_repository import (
    SqlAlchemyInstrumentAnalysisRepository,
)
from api.repositories.sqlalchemy_instrument_routing_repository import (
    SqlAlchemyInstrumentRoutingRepository,
)
from api.repositories.sqlalchemy_price_bar_repository import (
    SqlAlchemyPriceBarRepository,
)
from api.repositories.sqlalchemy_reference_rate_repository import (
    SqlAlchemyReferenceRateRepository,
)
from api.services.binance_spot_service import BinanceSpotService
from api.services.company_price_service import CompanyPriceService
from api.services.reference_rate_service import ReferenceRateService
from trading_engine.data.yfinance_loader import YFinanceLoader


OVERLAP_DAYS = 7
def refresh_instrument(instrument_id: int, mode: str) -> None:
    engine = create_db_engine()
    with Session(engine) as session:
        instrument = SqlAlchemyInstrumentAnalysisRepository(session).get_instrument(
            instrument_id
        )
        routing_metadata = SqlAlchemyInstrumentRoutingRepository(
            session
        ).get_instrument_route_metadata(instrument_id)
    if instrument is None:
        raise RuntimeError(f"Unknown instrument: {instrument_id}")
    if routing_metadata is None:
        raise RuntimeError(f"Missing routing metadata: {instrument_id}")
    route = resolve_instrument_data_route(routing_metadata)
    print(f"INSTRUMENT {instrument_id}: 0/1 {instrument.symbol}", flush=True)
    if route.fundamental_adapter is not None:
        _refresh_equity(engine, instrument, route, mode)
    elif route.price_adapter == "binance_spot":
        _refresh_binance_spot(engine, instrument, route, mode)
    elif instrument.instrument_type == "reference_rate":
        _refresh_reference_rate(engine, instrument, route, mode)
    else:
        raise RuntimeError(
            f"No price update adapter for instrument {instrument_id} ({instrument.symbol})"
        )
    print(f"INSTRUMENT {instrument_id}: 1/1 updated {instrument.symbol}", flush=True)


def _refresh_equity(
    engine, instrument, route: InstrumentDataRoute, mode: str
) -> None:
    now = datetime.now(UTC)
    end = latest_completed_venue_session(now, route.schedule)
    start = (
        route.full_history_start
        if mode == "full" or instrument.last_date is None
        else instrument.last_date - timedelta(days=OVERLAP_DAYS)
    )
    loader = (
        YFinanceLoader()
        if route.price_adapter == "yfinance"
        else VietnamPriceLoader()
    )
    prices = loader.load(route.provider_symbol, start, end + timedelta(days=1))
    with session_scope(engine) as session:
        CompanyPriceService(
            SqlAlchemyPriceBarRepository(session),
            SqlAlchemyInstrumentRoutingRepository(session),
        ).store_downloaded_histories(
            {instrument.id: prices},
            fetched_at=now,
        )


def _refresh_reference_rate(
    engine, instrument, route: InstrumentDataRoute, mode: str
) -> None:
    with Session(engine) as session:
        record = ReferenceRateService(
            SqlAlchemyReferenceRateRepository(session)
        ).get_instrument(route.provider_symbol)
    if record is None:
        raise RuntimeError(f"Unknown reference rate: {instrument.symbol}")
    end = datetime.now(UTC).date() - timedelta(days=1)
    start = (
        route.full_history_start
        if mode == "full" or record.last_date is None
        else record.last_date - timedelta(days=OVERLAP_DAYS)
    )
    prices = YFinanceLoader().load(
        route.provider_symbol, start, end + timedelta(days=1)
    )
    with session_scope(engine) as session:
        ReferenceRateService(
            SqlAlchemyReferenceRateRepository(session),
            SqlAlchemyPriceBarRepository(session),
        ).store_history(record, prices, fetched_at=datetime.now(UTC))


def _refresh_binance_spot(
    engine, instrument, route: InstrumentDataRoute, mode: str
) -> None:
    with Session(engine) as session:
        records = BinanceSpotService(
            SqlAlchemyCryptoMarketRepository(session)
        ).list_instruments(symbols=(route.provider_symbol,))
    if len(records) != 1:
        raise RuntimeError(f"Unknown Binance Spot instrument: {instrument.symbol}")
    record = records[0]
    end = datetime.now(UTC).date() - timedelta(days=1)
    start = (
        route.full_history_start
        if mode == "full" or record.last_date is None
        else record.last_date - timedelta(days=OVERLAP_DAYS)
    )
    with BinanceSpotClient() as rest_client, BinancePublicDataClient() as archive_client:
        klines = BinanceSpotHistoryLoader(rest_client, archive_client).load(
            record.symbol, start, end, source="auto"
        )
    with session_scope(engine) as session:
        BinanceSpotService(
            SqlAlchemyCryptoMarketRepository(session),
            SqlAlchemyPriceBarRepository(session),
        ).store_history(record, klines, fetched_at=datetime.now(UTC))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instrument-id", type=int, required=True)
    parser.add_argument("--mode", choices=("incremental", "full"), default="incremental")
    args = parser.parse_args()
    refresh_instrument(args.instrument_id, args.mode)


if __name__ == "__main__":
    main()
