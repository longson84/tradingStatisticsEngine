"""Synchronize the Binance Spot catalog and optional daily price history.

Catalog only (safe default):
    uv run --no-sync python -m scripts.sync_binance_spot

Backfill selected instruments using archives plus REST for uncovered dates:
    uv run --no-sync python -m scripts.sync_binance_spot \
        --history --symbols BTCUSDT,ETHUSDT --start 2017-08-17

Incrementally refresh instruments that already have stored coverage:
    uv run --no-sync python -m scripts.sync_binance_spot \
        --history --symbols BTCUSDT,ETHUSDT
"""
from __future__ import annotations

import argparse
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.orm import Session

from api.db.session import create_db_engine, database_url, session_scope
from api.providers.binance_spot import (
    BinancePublicDataClient,
    BinanceSpotClient,
    BinanceSpotHistoryLoader,
)
from api.repositories.sqlalchemy_crypto_market_repository import (
    SqlAlchemyCryptoMarketRepository,
)
from api.repositories.sqlalchemy_price_bar_repository import (
    SqlAlchemyPriceBarRepository,
)
from api.services.binance_spot_service import BinanceSpotService


DEFAULT_FULL_START = date(2017, 8, 17)
INCREMENTAL_OVERLAP_DAYS = 7


def main() -> None:
    args = _parse_args()
    engine = create_db_engine(args.database_url)

    with BinanceSpotClient() as rest_client:
        catalog = rest_client.fetch_catalog()
        with session_scope(engine) as session:
            result = BinanceSpotService(
                SqlAlchemyCryptoMarketRepository(session)
            ).sync_catalog(catalog)
        print(
            "Binance Spot catalog synchronized: "
            f"received={result.received_instruments} "
            f"active={result.active_instruments} "
            f"added={result.added_instruments} "
            f"updated={result.updated_instruments} "
            f"deactivated={result.deactivated_instruments} "
            f"assets_added={result.added_assets}"
        )
        if not args.history:
            return

        symbols = _csv_values(args.symbols)
        quote_assets = _csv_values(args.quote_assets)
        if not symbols and not quote_assets:
            raise SystemExit(
                "--history requires --symbols or --quote-assets to avoid an "
                "accidental all-market backfill"
            )
        with Session(engine) as session:
            instruments = BinanceSpotService(
                SqlAlchemyCryptoMarketRepository(session)
            ).list_instruments(symbols=symbols, quote_assets=quote_assets)
        if symbols:
            missing = sorted(set(symbols) - {row.symbol for row in instruments})
            if missing:
                raise SystemExit(
                    f"Unknown or inactive Binance Spot symbols: {missing}"
                )
        if len(instruments) > args.max_symbols:
            raise SystemExit(
                f"Selection contains {len(instruments)} instruments; "
                f"increase --max-symbols from {args.max_symbols} explicitly"
            )

        end = args.end or (datetime.now(UTC).date() - timedelta(days=1))
        archive_client = (
            BinancePublicDataClient() if args.source in {"auto", "archive"} else None
        )
        try:
            loader = BinanceSpotHistoryLoader(rest_client, archive_client)
            for instrument in instruments:
                start = _requested_start(instrument.last_date, args.start)
                if start > end:
                    print(
                        f"{instrument.symbol}: current through "
                        f"{instrument.last_date}; no download required"
                    )
                    continue
                klines = loader.load(
                    instrument.symbol,
                    start,
                    end,
                    source=args.source,
                )
                fetched_at = datetime.now(UTC)
                with session_scope(engine) as session:
                    service = BinanceSpotService(
                        SqlAlchemyCryptoMarketRepository(session),
                        SqlAlchemyPriceBarRepository(session),
                    )
                    write = service.store_history(
                        instrument,
                        klines,
                        fetched_at=fetched_at,
                    )
                print(
                    f"{instrument.symbol}: {start}..{end} "
                    f"received={write.input_rows} "
                    f"rejected={write.rejected_rows} "
                    f"stored={write.stored_rows}"
                )
        finally:
            if archive_client is not None:
                archive_client.close()


def _requested_start(last_date: date | None, explicit: date | None) -> date:
    if explicit is not None:
        return explicit
    if last_date is not None:
        return last_date - timedelta(days=INCREMENTAL_OVERLAP_DAYS)
    return DEFAULT_FULL_START


def _csv_values(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(
        dict.fromkeys(
            item.upper().strip() for item in value.split(",") if item.strip()
        )
    )


def _date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected an ISO date (YYYY-MM-DD)") from exc


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        default=database_url(),
        help="SQLAlchemy database URL (defaults to DATABASE_URL)",
    )
    parser.add_argument(
        "--history",
        action="store_true",
        help="also load daily history; catalog synchronization is always performed",
    )
    parser.add_argument("--symbols", help="comma-separated Binance symbols")
    parser.add_argument("--quote-assets", help="comma-separated quote assets")
    parser.add_argument("--start", type=_date, help="history start date")
    parser.add_argument(
        "--end",
        type=_date,
        help="history end date; defaults to yesterday UTC",
    )
    parser.add_argument(
        "--source",
        choices=("auto", "archive", "rest"),
        default="auto",
        help="auto uses monthly archives and REST for uncovered dates",
    )
    parser.add_argument(
        "--max-symbols",
        type=int,
        default=25,
        help="safety limit for one history run",
    )
    args = parser.parse_args()
    if args.max_symbols < 1:
        parser.error("--max-symbols must be positive")
    if args.start and args.end and args.start > args.end:
        parser.error("--start must not be after --end")
    return args


if __name__ == "__main__":
    main()
