"""Import one official SEC quarterly Form 13F ZIP archive."""
from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import Engine

from api.adapters.sec_13f import Sec13FArchive
from api.db.session import create_db_engine, session_scope
from api.repositories.sqlalchemy_institutional_activity_repository import (
    SqlAlchemyInstitutionalActivityRepository,
)
from api.services.institutional_activity_write_service import (
    InstitutionalActivityWriteService,
)


def refresh_institutional_activity(
    archive_path: Path,
    *,
    engine: Engine | None = None,
    fetched_at: datetime | None = None,
) -> str:
    if not archive_path.is_file():
        raise ValueError(f"SEC 13F archive does not exist: {archive_path}")
    fetched = fetched_at or datetime.now(UTC)
    if fetched.utcoffset() is None:
        raise ValueError("fetched_at must be timezone-aware")
    db_engine = engine or create_db_engine()
    with archive_path.open("rb") as stream, session_scope(db_engine) as session:
        result = InstitutionalActivityWriteService(
            SqlAlchemyInstitutionalActivityRepository(session)
        ).import_archive(Sec13FArchive(stream, fetched_at=fetched))
    return (
        f"imported {result.submissions} SEC 13F submissions and "
        f"{result.positions_seen} positions: {result.mapped_positions} mapped, "
        f"{result.unmapped_positions} unmapped, "
        f"{result.ambiguous_positions} ambiguous, "
        f"{result.rejected_positions} rejected, {result.option_positions} options; "
        f"{result.positions_added} new source rows"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="Official SEC quarterly Form 13F ZIP")
    args = parser.parse_args()
    print(refresh_institutional_activity(args.archive))


if __name__ == "__main__":
    main()
