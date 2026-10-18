from __future__ import annotations

from datetime import UTC, date, datetime, time
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from api.db.models import Base, Company, Instrument, InstrumentFlowObservation, Venue
from api.repositories.instrument_flow_repository import (
    InstrumentFlowQuery,
    InstrumentFlowWriteRecord,
)
from api.repositories.sqlalchemy_instrument_flow_repository import (
    SqlAlchemyInstrumentFlowRepository,
)


def _database():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    venue = Venue(
        code="HOSE", name="Ho Chi Minh Stock Exchange", venue_type="exchange",
        country_code="VN", timezone_name="Asia/Ho_Chi_Minh",
        trading_calendar_code="VN_EQUITIES", session_cutoff_time=time(15, 15),
        is_active=True, source="test",
    )
    instrument = Instrument(
        company=Company(display_name="FPT", source="test"),
        venue=venue,
        symbol="FPT",
        instrument_type="common_stock",
        currency="VND",
        source="test",
    )
    session.add(instrument)
    session.flush()
    return session, instrument


def _record(instrument_id: int, trading_date: date, **overrides: object):
    values: dict[str, object] = {
        "instrument_id": instrument_id,
        "trading_date": trading_date,
        "participant_type": "foreign",
        "buy_volume": Decimal("100"),
        "buy_value": Decimal("1000"),
        "sell_volume": Decimal("40"),
        "sell_value": Decimal("300"),
        "net_volume": Decimal("60"),
        "net_value": Decimal("700"),
        "currency": "VND",
        "source": "vnstock-5.1.0-vci",
        "fetched_at": datetime(2026, 10, 18, tzinfo=UTC),
    }
    values.update(overrides)
    return InstrumentFlowWriteRecord(**values)  # type: ignore[arg-type]


def test_repository_upserts_corrections_and_rebuilds_coverage():
    session, instrument = _database()
    repository = SqlAlchemyInstrumentFlowRepository(session)
    try:
        repository.upsert_observations([
            _record(instrument.id, date(2026, 10, 14)),
            _record(instrument.id, date(2026, 10, 16)),
        ])
        repository.upsert_observations([
            _record(
                instrument.id,
                date(2026, 10, 16),
                net_value=Decimal("999"),
                fetched_at=datetime(2026, 10, 19, tzinfo=UTC),
            )
        ])
        session.commit()

        rows = tuple(repository.iter_observations(InstrumentFlowQuery(
            instrument_id=instrument.id,
            participant_type="foreign",
            start=date(2026, 10, 15),
            end=date(2026, 10, 16),
        )))
        coverage = repository.get_coverage(instrument.id, "foreign")
    finally:
        session.close()

    assert [row.trading_date for row in rows] == [date(2026, 10, 16)]
    assert rows[0].net_value == Decimal("999.000000")
    assert coverage is not None
    assert coverage.first_date == date(2026, 10, 14)
    assert coverage.last_date == date(2026, 10, 16)
    assert coverage.row_count == 2
    assert coverage.source == "vnstock-5.1.0-vci"
    assert coverage.fetched_at == datetime(2026, 10, 19)


def test_repository_keeps_participant_coverages_independent():
    session, instrument = _database()
    repository = SqlAlchemyInstrumentFlowRepository(session)
    try:
        repository.upsert_observations([
            _record(instrument.id, date(2026, 10, 14), participant_type="foreign"),
            _record(instrument.id, date(2026, 10, 16), participant_type="proprietary"),
        ])
        session.commit()
        foreign = repository.get_coverage(instrument.id, "foreign")
        proprietary = repository.get_coverage(instrument.id, "proprietary")
    finally:
        session.close()

    assert foreign is not None and foreign.row_count == 1
    assert proprietary is not None and proprietary.row_count == 1


def test_repository_rollback_keeps_observations_and_coverage_unchanged():
    session, instrument = _database()
    repository = SqlAlchemyInstrumentFlowRepository(session)
    try:
        repository.upsert_observations([_record(instrument.id, date(2026, 10, 14))])
        session.commit()
        repository.upsert_observations([
            _record(instrument.id, date(2026, 10, 16), net_value=Decimal("999"))
        ])
        session.rollback()

        rows = tuple(repository.iter_observations(InstrumentFlowQuery(
            instrument_id=instrument.id,
            participant_type="foreign",
        )))
        coverage = repository.get_coverage(instrument.id, "foreign")
    finally:
        session.close()

    assert [row.trading_date for row in rows] == [date(2026, 10, 14)]
    assert coverage is not None and coverage.row_count == 1


def test_repository_rejects_unknown_instrument_without_partial_write():
    session, _ = _database()
    repository = SqlAlchemyInstrumentFlowRepository(session)
    try:
        with pytest.raises(ValueError, match="unknown instruments"):
            repository.upsert_observations([_record(999, date(2026, 10, 16))])
        assert session.scalar(select(InstrumentFlowObservation.id)) is None
    finally:
        session.close()
