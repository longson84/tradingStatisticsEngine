from datetime import UTC, datetime

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from api.db.models import Base, InstitutionalFiling, InstitutionalFilingPosition
from scripts.refresh_institutional_activity import refresh_institutional_activity
from tests.api.test_sec_13f_adapter import archive_bytes


def test_refresh_imports_a_local_official_archive_atomically(tmp_path) -> None:
    archive = tmp_path / "13f.zip"
    archive.write_bytes(archive_bytes())
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    detail = refresh_institutional_activity(
        archive,
        engine=engine,
        fetched_at=datetime(2026, 9, 14, 3, tzinfo=UTC),
    )

    assert detail == (
        "imported 1 SEC 13F submissions and 1 positions: "
        "0 mapped, 1 unmapped, 0 ambiguous, 0 rejected, 0 options; "
        "1 new source rows"
    )
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(InstitutionalFiling)) == 1
        assert session.scalar(select(func.count()).select_from(InstitutionalFilingPosition)) == 1
    engine.dispose()
