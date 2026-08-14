"""Synchronize canonical reference-rate instruments and optional history.

Catalog only (safe default):
    uv run --no-sync python -m scripts.sync_reference_rates

Backfill all registered daily histories from Yahoo Finance through yfinance:
    uv run --no-sync python -m scripts.sync_reference_rates --history

Backfill only ETH/USD:
    uv run --no-sync python -m scripts.sync_reference_rates \
        --history --symbols ETH-USD
"""
from __future__ import annotations

import argparse
from datetime import UTC, date, datetime, timedelta

from api.db.session import create_db_engine, database_url, session_scope
from api.repositories.sqlalchemy_price_bar_repository import (
    SqlAlchemyPriceBarRepository,
)
from api.repositories.sqlalchemy_reference_rate_repository import (
    SqlAlchemyReferenceRateRepository,
)
from api.services.reference_rate_service import (
    ReferenceRateService,
    YAHOO_REFERENCE_RATES,
)
from trading_engine.data.yfinance_loader import YFinanceLoader


DEFAULT_FULL_STARTS = {
    "BTC-USD": date(2014, 9, 17),
    "ETH-USD": date(2015, 8, 7),
}
INCREMENTAL_OVERLAP_DAYS = 7


def main() -> None:
    args = _parse_args()
    engine = create_db_engine(args.database_url)
    requested_symbols = _csv_values(args.symbols) or tuple(
        row.symbol for row in YAHOO_REFERENCE_RATES
    )
    with session_scope(engine) as session:
        instruments = ReferenceRateService(
            SqlAlchemyReferenceRateRepository(session)
        ).sync_catalog(requested_symbols)
    for instrument in instruments:
        print(
            "Reference-rate catalog synchronized: "
            f"instrument={instrument.symbol} "
            f"base={instrument.base_asset} quote={instrument.quote_asset} venue=none"
        )
    if not args.history:
        return

    end = args.end or (datetime.now(UTC).date() - timedelta(days=1))
    for instrument in instruments:
        start = args.start or (
            instrument.last_date - timedelta(days=INCREMENTAL_OVERLAP_DAYS)
            if instrument.last_date else DEFAULT_FULL_STARTS[instrument.symbol]
        )
        if start > end:
            print(
                f"{instrument.symbol}: current through {instrument.last_date}; "
                "no download required"
            )
            continue

        # yfinance treats end as exclusive; this interface treats it as inclusive.
        prices = YFinanceLoader().load(
            instrument.symbol, start, end + timedelta(days=1)
        )
        fetched_at = datetime.now(UTC)
        with session_scope(engine) as session:
            result = ReferenceRateService(
                SqlAlchemyReferenceRateRepository(session),
                SqlAlchemyPriceBarRepository(session),
            ).store_history(instrument, prices, fetched_at=fetched_at)
        first_returned = prices.data.index.min().date()
        last_returned = prices.data.index.max().date()
        print(
            f"{instrument.symbol}: requested={start}..{end} "
            f"returned={first_returned}..{last_returned} "
            "provider=Yahoo Finance adapter=yfinance "
            f"received={result.input_rows} rejected={result.rejected_rows} "
            f"stored={result.stored_rows}"
        )


def _date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected an ISO date (YYYY-MM-DD)") from exc


def _csv_values(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(
        dict.fromkeys(
            item.upper().strip() for item in value.split(",") if item.strip()
        )
    )


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
    parser.add_argument(
        "--symbols",
        help="comma-separated registered symbols; defaults to all reference rates",
    )
    parser.add_argument("--start", type=_date, help="inclusive history start date")
    parser.add_argument(
        "--end",
        type=_date,
        help="inclusive history end date; defaults to yesterday UTC",
    )
    args = parser.parse_args()
    if args.start and args.end and args.start > args.end:
        parser.error("--start must not be after --end")
    return args


if __name__ == "__main__":
    main()
