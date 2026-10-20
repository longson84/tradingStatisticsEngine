from datetime import UTC, datetime
from io import BytesIO

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from api.adapters.sec_13f import Sec13FArchive
from api.db.models import Base, InstitutionalFilingPosition, Instrument
from api.repositories.institutional_activity_repository import InstrumentIdentifierWrite
from api.repositories.sqlalchemy_institutional_activity_repository import SqlAlchemyInstitutionalActivityRepository
from api.services.institutional_activity_write_service import InstitutionalActivityWriteService
from tests.api.test_sec_13f_adapter import archive_bytes


def test_write_service_imports_idempotently_and_reports_verified_mapping() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        instrument = Instrument(symbol="AAPL", currency="USD", source="test")
        session.add(instrument)
        session.flush()
        repository = SqlAlchemyInstitutionalActivityRepository(session)
        repository.add_identifier(InstrumentIdentifierWrite(
            instrument_id=instrument.id,
            namespace="cusip",
            value="037833100",
            valid_from=None,
            valid_to=None,
            source="manual-verified",
            verified_at=datetime(2026, 8, 1, tzinfo=UTC),
        ))
        service = InstitutionalActivityWriteService(repository)
        archive = Sec13FArchive(
            BytesIO(archive_bytes()),
            fetched_at=datetime(2026, 9, 14, 3, tzinfo=UTC),
        )

        first = service.import_archive(archive)
        second = service.import_archive(archive)
        session.commit()

        assert first.submissions == 1
        assert first.positions_added == 1
        assert first.mapped_positions == 1
        assert first.unmapped_positions == 0
        assert second.positions_added == 0
        assert session.scalar(select(func.count()).select_from(InstitutionalFilingPosition)) == 1
        stored = session.scalar(select(InstitutionalFilingPosition))
        assert stored.instrument_id == instrument.id
        assert stored.raw_figi == "BBG000B9XRY4"
        assert stored.reported_value_unit == "USD_thousands"
    engine.dispose()
