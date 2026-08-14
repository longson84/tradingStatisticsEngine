"""Synchronize live equity Universes directly into canonical PostgreSQL tables.

Examples:
    uv run python -m scripts.sync_equity_universes --all
    uv run python -m scripts.sync_equity_universes --listing-country vn --dry-run
    uv run python -m scripts.sync_equity_universes --universe US500 --force
"""
from __future__ import annotations

import argparse
from collections.abc import Sequence

from api.db.session import create_db_engine
from api.providers.nasdaq_symbol_directory import NasdaqSymbolDirectoryClient
from api.providers.universe_catalog import create_universe_provider_registry
from api.repositories.sqlalchemy_universe_sync_repository import (
    SqlAlchemyUniverseSyncRepository,
)
from api.services.universe_sync_service import (
    ALL_UNIVERSE_ORDER,
    US_UNIVERSE_ORDER,
    VN_UNIVERSE_FAMILY,
    UniverseSyncService,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch current equity Universe membership and synchronize it "
            "directly into PostgreSQL."
        )
    )
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--all", action="store_true")
    selection.add_argument("--listing-country", choices=("us", "vn"))
    selection.add_argument(
        "--universe",
        action="append",
        metavar="CODE",
        help="Universe code; repeat to select more than one.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--database-url", default=None)
    return parser


def selected_universes(args: argparse.Namespace) -> tuple[str, ...]:
    if args.all:
        return ALL_UNIVERSE_ORDER
    if args.listing_country == "us":
        return US_UNIVERSE_ORDER
    if args.listing_country == "vn":
        return VN_UNIVERSE_FAMILY
    return tuple(args.universe or ())


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    engine = create_db_engine(args.database_url)
    repository = SqlAlchemyUniverseSyncRepository(engine)
    providers = create_universe_provider_registry()

    def fetch_us_listing_catalog():
        with NasdaqSymbolDirectoryClient() as client:
            return client.fetch_catalog()

    service = UniverseSyncService(
        repository,
        providers,
        us_listing_catalog_fetcher=fetch_us_listing_catalog,
    )
    results = service.synchronize(
        selected_universes(args),
        dry_run=args.dry_run,
        force=args.force,
    )
    mode = "DRY RUN" if args.dry_run else "UPDATED"
    for result in results:
        print(
            f"{result.universe_code}: {mode} received={result.received_count} "
            f"added={result.added_count} removed={result.removed_count} "
            f"unchanged={result.unchanged_count} "
            f"metadata={result.metadata_change_count}"
        )


if __name__ == "__main__":
    main()
