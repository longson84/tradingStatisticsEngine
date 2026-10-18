from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from api.db.models import (
    Base,
    Company,
    Instrument,
    InstrumentSessionStatisticSnapshot,
)
from api.repositories.session_statistics_repository import (
    SessionStatisticSnapshotWrite,
)
from api.repositories.sqlalchemy_session_statistics_repository import (
    SqlAlchemySessionStatisticsRepository,
)
from api.session_statistics import (
    SESSION_STATISTIC_METRIC_CODES,
    SESSION_STATISTIC_SCHEMA_VERSION,
)


def _values(offset: int = 0):
    return {
        code: Decimal(index + offset)
        for index, code in enumerate(SESSION_STATISTIC_METRIC_CODES, 1)
    }


def _write(instrument_id: int, fetched_at: datetime, *, offset: int = 0):
    return SessionStatisticSnapshotWrite(
        instrument_id=instrument_id,
        period_start=date(2026, 10, 15),
        period_end=date(2026, 10, 16),
        source="vnstock-5.1.0-vci",
        schema_version=SESSION_STATISTIC_SCHEMA_VERSION,
        fetched_at=fetched_at,
        metrics=_values(offset),
    )


def _repository():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    instrument = Instrument(
        company=Company(display_name="FPT", source="test"),
        symbol="FPT",
        instrument_type="common_stock",
        currency="VND",
        source="test",
    )
    session.add(instrument)
    session.commit()
    return session, instrument.id, SqlAlchemySessionStatisticsRepository(session)


def test_repository_stores_complete_snapshot_and_returns_newest_exact_period():
    session, instrument_id, repository = _repository()
    try:
        first = datetime(2026, 10, 18, 8, tzinfo=UTC)
        repository.store_snapshot(_write(instrument_id, first))
        repository.store_snapshot(_write(
            instrument_id, first + timedelta(minutes=1), offset=100,
        ))
        session.commit()

        result = repository.get_latest_snapshot(
            instrument_id, date(2026, 10, 15), date(2026, 10, 16)
        )
        assert result is not None
        assert result.fetched_at.replace(tzinfo=UTC) == first + timedelta(minutes=1)
        assert len(result.metrics) == 64
        assert result.metrics[0].code == "average_match_volume"
        assert result.metrics[0].value == Decimal("101.000000")
        assert session.scalar(select(func.count()).select_from(
            InstrumentSessionStatisticSnapshot
        )) == 2
        assert repository.get_latest_snapshot(
            instrument_id, date(2026, 10, 14), date(2026, 10, 16)
        ) is None
    finally:
        session.close()


def test_repository_rejects_incomplete_metrics_without_inserting_snapshot():
    session, instrument_id, repository = _repository()
    try:
        values = _values()
        values.pop("total_value")
        record = _write(instrument_id, datetime(2026, 10, 18, tzinfo=UTC))
        record = SessionStatisticSnapshotWrite(
            **{**record.__dict__, "metrics": values}
        )

        with pytest.raises(ValueError, match="exactly 64"):
            repository.store_snapshot(record)

        assert session.scalar(select(func.count()).select_from(
            InstrumentSessionStatisticSnapshot
        )) == 0
    finally:
        session.close()


def test_repository_delete_instrument_cascades_snapshots_via_relationship():
    session, instrument_id, repository = _repository()
    try:
        repository.store_snapshot(_write(
            instrument_id, datetime(2026, 10, 18, tzinfo=UTC)
        ))
        session.commit()
        instrument = session.get(Instrument, instrument_id)
        assert instrument is not None
        session.delete(instrument)
        session.commit()

        assert session.scalar(select(func.count()).select_from(
            InstrumentSessionStatisticSnapshot
        )) == 0
    finally:
        session.close()
