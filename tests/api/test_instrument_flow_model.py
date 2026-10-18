from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.db.models import (
    Base,
    Company,
    DataOperationBatchStep,
    DataOperationRun,
    Instrument,
    InstrumentFlowObservation,
)


def _instrument() -> Instrument:
    return Instrument(
        company=Company(display_name="FPT", source="test"),
        symbol="FPT",
        instrument_type="common_stock",
        currency="VND",
        source="test",
    )


def _observation(instrument_id: int, **overrides: object) -> InstrumentFlowObservation:
    values: dict[str, object] = {
        "instrument_id": instrument_id,
        "trading_date": date(2026, 10, 16),
        "participant_type": "foreign",
        "buy_volume": Decimal("1390717.000000"),
        "buy_value": Decimal("81156580000.125000"),
        "sell_volume": Decimal("568508.000000"),
        "sell_value": Decimal("33224080000.000000"),
        "net_volume": Decimal("822209.000000"),
        "net_value": Decimal("-47932500000.125000"),
        "currency": "VND",
        "source": "vnstock-5.1.0-vci",
        "fetched_at": datetime(2026, 10, 18, tzinfo=UTC),
    }
    values.update(overrides)
    return InstrumentFlowObservation(**values)  # type: ignore[arg-type]


def test_instrument_flow_round_trip_preserves_fixed_point_values_and_signed_nets():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        instrument = _instrument()
        session.add(instrument)
        session.flush()
        session.add(_observation(instrument.id))
        session.commit()

        stored = session.scalar(select(InstrumentFlowObservation))
        assert stored is not None
        assert stored.buy_value == Decimal("81156580000.125000")
        assert stored.net_value == Decimal("-47932500000.125000")
        assert stored.instrument.symbol == "FPT"


def test_instrument_flow_identity_allows_participants_but_rejects_duplicate_type():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        instrument = _instrument()
        session.add(instrument)
        session.flush()
        session.add_all([
            _observation(instrument.id, participant_type="foreign"),
            _observation(instrument.id, participant_type="proprietary"),
        ])
        session.commit()
        assert len(session.scalars(select(InstrumentFlowObservation)).all()) == 2

        session.add(_observation(instrument.id, participant_type="foreign"))
        with pytest.raises(IntegrityError):
            session.commit()


@pytest.mark.parametrize(
    "overrides",
    [
        {"participant_type": "retail"},
        {"buy_volume": Decimal("-1")},
        {"buy_value": Decimal("-1")},
        {"sell_volume": Decimal("-1")},
        {"sell_value": Decimal("-1")},
    ],
)
def test_instrument_flow_rejects_unsupported_participants_and_negative_gross_values(
    overrides: dict[str, object],
):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        instrument = _instrument()
        session.add(instrument)
        session.flush()
        session.add(_observation(instrument.id, **overrides))
        with pytest.raises(IntegrityError):
            session.commit()


def test_operation_models_keep_session_stats_out_of_batch_datasets():
    run_constraint = next(
        constraint for constraint in DataOperationRun.__table__.constraints
        if constraint.name == "ck_data_operation_runs_dataset"
    )
    step_constraint = next(
        constraint for constraint in DataOperationBatchStep.__table__.constraints
        if constraint.name == "ck_data_operation_batch_steps_dataset"
    )

    assert "foreign_flow" in str(run_constraint.sqltext)
    assert "foreign_flow" in str(step_constraint.sqltext)
    assert "proprietary_flow" in str(run_constraint.sqltext)
    assert "proprietary_flow" in str(step_constraint.sqltext)
    assert "session_stats" in str(run_constraint.sqltext)
    assert "session_stats" not in str(step_constraint.sqltext)
