"""Import and verify saved company universes in PostgreSQL.

Usage:
    uv run python -m scripts.import_companies
    uv run python -m scripts.import_companies --verify-only
"""
from __future__ import annotations

import argparse

from api.db.company_import import import_company_universes, verify_company_universes
from api.db.session import create_db_engine


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    engine = create_db_engine(args.database_url)
    result = (
        verify_company_universes(engine)
        if args.verify_only
        else import_company_universes(engine)
    )
    print(f"instruments: {result.instruments}")
    for market, count in sorted(result.markets.items()):
        print(f"{market}: {count}")
    failed = False
    for universe in result.universes:
        status = "OK" if universe.expected_members == universe.stored_members else "MISMATCH"
        print(
            f"{universe.universe}: expected={universe.expected_members} "
            f"stored={universe.stored_members} {status}"
        )
        failed = failed or status != "OK"
    if failed:
        raise SystemExit("Company universe verification failed")


if __name__ == "__main__":
    main()
