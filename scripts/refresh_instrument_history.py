"""Refresh canonical price history for one exact instrument ID."""
from __future__ import annotations

import argparse
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.engine import Engine
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
from api.services.instrument_price_write_service import InstrumentPriceWriteService
from api.services.reference_rate_service import ReferenceRateService
from api.services.price_refresh_service import PriceRefreshAttempt, PriceRefreshService
from trading_engine.data.yfinance_loader import YFinanceLoader


OVERLAP_DAYS = 7
def refresh_instrument(
    instrument_id: int,
    mode: str,
    *,
    engine: Engine | None = None,
    emit_progress: bool = True,
) -> str:
    db_engine = engine or create_db_engine()
    with Session(db_engine) as session:
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
    attempted_at = datetime.now(UTC)
    attempted_through = latest_completed_venue_session(attempted_at, route.schedule)
    if emit_progress:
        print(f"INSTRUMENT {instrument_id}: 0/1 {instrument.symbol}", flush=True)
    if mode == "incremental":
        reuse_detail = _incremental_reuse_detail(
            db_engine,
            instrument_id,
            route.price_basis,
            instrument.last_date,
            attempted_through,
        )
        if reuse_detail is not None:
            if emit_progress:
                print(
                    f"INSTRUMENT {instrument_id}: 1/1 {reuse_detail}",
                    flush=True,
                )
            return reuse_detail
    try:
        if route.fundamental_adapter is not None:
            selected_source = _refresh_equity(db_engine, instrument, route, mode)
        elif route.price_adapter == "binance_spot":
            selected_source = _refresh_binance_spot(
                db_engine, instrument, route, mode
            )
        elif instrument.instrument_type == "reference_rate":
            selected_source = _refresh_reference_rate(
                db_engine, instrument, route, mode
            )
        elif instrument.instrument_type == "market_index":
            selected_source = _refresh_market_index(
                db_engine, instrument, route, mode
            )
        else:
            raise RuntimeError(
                f"No price update adapter for instrument {instrument_id} "
                f"({instrument.symbol})"
            )
    except Exception as exc:
        _record_attempt(
            db_engine,
            instrument_id,
            route,
            attempted_through,
            None,
            "failed",
            None,
            str(exc),
            attempted_at,
        )
        raise
    returned_through = _last_stored_date(db_engine, instrument_id, route.price_basis)
    outcome = (
        "current"
        if returned_through is not None and returned_through >= attempted_through
        else "checked_no_new_bar"
    )
    _record_attempt(
        db_engine,
        instrument_id,
        route,
        attempted_through,
        returned_through,
        outcome,
        selected_source,
        None,
        attempted_at,
    )
    detail = f"{outcome} {instrument.symbol} through {returned_through or 'none'}"
    if emit_progress:
        print(f"INSTRUMENT {instrument_id}: 1/1 {detail}", flush=True)
    return detail


def _refresh_equity(
    engine, instrument, route: InstrumentDataRoute, mode: str
) -> str:
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
    return prices.source


def _refresh_reference_rate(
    engine, instrument, route: InstrumentDataRoute, mode: str
) -> str:
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
    return prices.source


def _refresh_binance_spot(
    engine, instrument, route: InstrumentDataRoute, mode: str
) -> str:
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
    return klines[-1].source if klines else route.price_adapter


def _refresh_market_index(
    engine: Engine,
    instrument,
    route: InstrumentDataRoute,
    mode: str,
) -> str:
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
        InstrumentPriceWriteService(
            SqlAlchemyPriceBarRepository(session),
            SqlAlchemyInstrumentRoutingRepository(session),
        ).store_history(instrument.id, prices, fetched_at=now)
    return prices.source


def _last_stored_date(
    engine: Engine,
    instrument_id: int,
    price_basis: str,
) -> date | None:
    with Session(engine) as session:
        rows = SqlAlchemyPriceBarRepository(session).list_instrument_coverages(
            (instrument_id,), price_basis
        )
    return rows[0].last_date if rows else None


def _incremental_reuse_detail(
    engine: Engine,
    instrument_id: int,
    price_basis: str,
    last_stored_date: date | None,
    expected_session: date,
) -> str | None:
    if last_stored_date is not None and last_stored_date >= expected_session:
        return f"reused current history through {last_stored_date}"
    with Session(engine) as session:
        states = SqlAlchemyPriceBarRepository(
            session
        ).list_instrument_refresh_states((instrument_id,), price_basis)
    if (
        states
        and states[0].attempted_through >= expected_session
        and states[0].outcome == "checked_no_new_bar"
    ):
        return (
            "reused provider check through "
            f"{states[0].attempted_through}"
        )
    return None


def _record_attempt(
    engine: Engine,
    instrument_id: int,
    route: InstrumentDataRoute,
    attempted_through: date,
    returned_through: date | None,
    outcome: str,
    selected_source: str | None,
    detail: str | None,
    attempted_at: datetime,
) -> None:
    with session_scope(engine) as session:
        PriceRefreshService(
            SqlAlchemyPriceBarRepository(session)
        ).record_attempts([PriceRefreshAttempt(
            instrument_id=instrument_id,
            price_basis=route.price_basis,
            attempted_through=attempted_through,
            returned_through=returned_through,
            outcome=outcome,
            primary_source=route.price_adapter,
            selected_source=selected_source,
            attempted_at=attempted_at,
            detail=detail,
        )])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instrument-id", type=int, required=True)
    parser.add_argument("--mode", choices=("incremental", "full"), default="incremental")
    args = parser.parse_args()
    refresh_instrument(args.instrument_id, args.mode)


if __name__ == "__main__":
    main()
