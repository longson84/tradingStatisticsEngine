"""Synchronize current US equity listing venues from Nasdaq Trader.

The official symbol directories are fetched in memory and reconciled directly
to canonical PostgreSQL instruments; no JSON or CSV snapshot is persisted.

Apply current venue assignments:
    uv run --no-sync python -m scripts.sync_equity_venues

Preview without committing:
    uv run --no-sync python -m scripts.sync_equity_venues --dry-run
"""
from __future__ import annotations

import argparse

from sqlalchemy.orm import Session

from api.db.session import create_db_engine, database_url
from api.providers.nasdaq_symbol_directory import NasdaqSymbolDirectoryClient
from api.repositories.sqlalchemy_equity_venue_repository import (
    SqlAlchemyEquityVenueRepository,
)
from api.services.equity_venue_service import EquityVenueService


def main() -> None:
    args = _parse_args()
    engine = create_db_engine(args.database_url)
    with NasdaqSymbolDirectoryClient() as client:
        catalog = client.fetch_catalog()
    with Session(engine) as session:
        result = EquityVenueService(
            SqlAlchemyEquityVenueRepository(session)
        ).sync_us_listing_venues(catalog)
        if args.dry_run:
            session.rollback()
        else:
            session.commit()

    print(
        "US equity venues "
        f"{'previewed' if args.dry_run else 'synchronized'}: "
        f"source={catalog.source} received={result.received_listings} "
        f"instruments={result.instrument_count} matched={result.matched_instruments} "
        f"updated={result.updated_instruments} unchanged={result.unchanged_instruments} "
        f"unresolved={len(result.unresolved_symbols)} "
        f"ambiguous={len(result.ambiguous_symbols)}"
    )
    if result.unresolved_symbols:
        print("Unresolved current symbols: " + ", ".join(result.unresolved_symbols))
    if result.ambiguous_symbols:
        print("Ambiguous current symbols: " + ", ".join(result.ambiguous_symbols))
    if args.fail_on_unresolved and (
        result.unresolved_symbols or result.ambiguous_symbols
    ):
        raise SystemExit(1)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        default=database_url(),
        help="SQLAlchemy database URL (defaults to DATABASE_URL)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="fetch and reconcile but roll back all database changes",
    )
    parser.add_argument(
        "--fail-on-unresolved",
        action="store_true",
        help="return a non-zero status when any active US symbol is unresolved",
    )
    return parser.parse_args()


if __name__ == "__main__":
    main()
