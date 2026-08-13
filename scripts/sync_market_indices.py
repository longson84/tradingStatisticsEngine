"""Refresh canonical PostgreSQL histories for registered market indices."""
from __future__ import annotations

import argparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.db.models import Instrument
from api.db.session import create_db_engine
from scripts.refresh_instrument_history import refresh_instrument


SUPPORTED_INDICES = ("SPX", "VN30")


def sync_market_indices(
    codes: tuple[str, ...],
    mode: str,
    *,
    database_url: str | None = None,
) -> None:
    engine = create_db_engine(database_url)
    normalized = tuple(dict.fromkeys(code.upper().strip() for code in codes))
    unknown = sorted(set(normalized) - set(SUPPORTED_INDICES))
    if unknown:
        raise ValueError(f"Unsupported market indices: {unknown}")
    with Session(engine) as session:
        rows = session.execute(
            select(Instrument.ticker, Instrument.id).where(
                Instrument.instrument_type == "market_index",
                Instrument.ticker.in_(normalized),
                Instrument.is_active.is_(True),
            )
        )
        instrument_ids = {ticker: instrument_id for ticker, instrument_id in rows}
    missing = sorted(set(normalized) - set(instrument_ids))
    if missing:
        raise RuntimeError(
            f"Missing canonical market-index instruments: {missing}. "
            "Run alembic upgrade head first."
        )
    for code in normalized:
        refresh_instrument(instrument_ids[code], mode, engine=engine)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--all", action="store_true")
    selection.add_argument(
        "--index",
        action="append",
        choices=tuple(code.lower() for code in SUPPORTED_INDICES),
        dest="indices",
    )
    parser.add_argument("--mode", choices=("incremental", "full"), default="incremental")
    parser.add_argument("--database-url", default=None)
    args = parser.parse_args()
    codes = SUPPORTED_INDICES if args.all else tuple(args.indices)
    sync_market_indices(codes, args.mode, database_url=args.database_url)


if __name__ == "__main__":
    main()
