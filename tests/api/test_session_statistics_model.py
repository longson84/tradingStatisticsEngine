from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.db.models import (
    Base,
    Company,
    Instrument,
    InstrumentSessionStatisticMetric,
    InstrumentSessionStatisticSnapshot,
)


def _instrument() -> Instrument:
    return Instrument(
        company=Company(display_name="FPT", source="test"),
        symbol="FPT",
        instrument_type="common_stock",
        currency="VND",
        source="test",
    )


def test_session_statistic_models_preserve_fixed_point_signed_values():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        instrument = _instrument()
        session.add(instrument)
        session.flush()
        snapshot = InstrumentSessionStatisticSnapshot(
            instrument_id=instrument.id,
            period_start=date(2026, 10, 15),
            period_end=date(2026, 10, 16),
            source="vnstock-5.1.0-vci",
            schema_version=1,
            fetched_at=datetime(2026, 10, 18, tzinfo=UTC),
        )
        snapshot.metrics.append(InstrumentSessionStatisticMetric(
            metric_code="fr_net_value_total",
            value=Decimal("-123.125000"),
        ))
        session.add(snapshot)
        session.commit()

        stored = session.scalar(select(InstrumentSessionStatisticMetric))
        assert stored is not None
        assert stored.value == Decimal("-123.125000")


@pytest.mark.parametrize(
    ("start", "end", "schema_version"),
    [
        (date(2026, 10, 17), date(2026, 10, 16), 1),
        (date(2026, 10, 15), date(2026, 10, 16), 0),
    ],
)
def test_session_statistic_snapshot_rejects_invalid_period_or_schema(
    start: date, end: date, schema_version: int,
):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        instrument = _instrument()
        session.add(instrument)
        session.flush()
        session.add(InstrumentSessionStatisticSnapshot(
            instrument_id=instrument.id,
            period_start=start,
            period_end=end,
            source="test",
            schema_version=schema_version,
            fetched_at=datetime(2026, 10, 18, tzinfo=UTC),
        ))
        with pytest.raises(IntegrityError):
            session.commit()


def test_session_statistic_metric_identity_is_unique_per_snapshot():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        instrument = _instrument()
        session.add(instrument)
        session.flush()
        snapshot = InstrumentSessionStatisticSnapshot(
            instrument_id=instrument.id,
            period_start=date(2026, 10, 15),
            period_end=date(2026, 10, 16),
            source="test",
            schema_version=1,
            fetched_at=datetime(2026, 10, 18, tzinfo=UTC),
        )
        snapshot.metrics.extend([
            InstrumentSessionStatisticMetric(metric_code="total_value", value=1),
            InstrumentSessionStatisticMetric(metric_code="total_value", value=2),
        ])
        session.add(snapshot)
        with pytest.raises(IntegrityError):
            session.commit()

