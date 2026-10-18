from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import Numeric, create_engine, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.db.models import Base, Instrument, InstrumentDailyTradeStatistic
from api.trade_statistics import TRADE_STATISTIC_STORAGE_COLUMNS


def _values(instrument_id: int, **overrides):
    return {
        "instrument_id": instrument_id,
        "trading_date": date(2026, 10, 16),
        "source": "vnstock-5.1.0-vci",
        "schema_version": 1,
        "fetched_at": datetime(2026, 10, 18, tzinfo=UTC),
        **{name: Decimal("1.000000") for name in TRADE_STATISTIC_STORAGE_COLUMNS},
        **overrides,
    }


@pytest.fixture
def database():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        instrument = Instrument(symbol="FPT", currency="VND", source="test")
        session.add(instrument)
        session.commit()
        yield session, instrument.id
    engine.dispose()


def test_trade_statistics_model_preserves_signed_net_and_exact_fixed_point(database):
    session, instrument_id = database
    session.add(InstrumentDailyTradeStatistic(**_values(
        instrument_id,
        market_cap=Decimal("12345678901234567890123456789012.123456"),
        average_buy_trade_volume=Decimal("123456789012345.123456"),
        total_net_trade_volume=Decimal("-123.123456"),
    )))
    session.commit()
    session.expire_all()
    row = session.scalar(select(InstrumentDailyTradeStatistic))
    assert row.market_cap == Decimal("12345678901234567890123456789012.123456")
    assert row.average_buy_trade_volume == Decimal("123456789012345.123456")
    assert row.total_net_trade_volume == Decimal("-123.123456")
    for name in TRADE_STATISTIC_STORAGE_COLUMNS:
        column = InstrumentDailyTradeStatistic.__table__.c[name]
        implementation = column.type.dialect_impl(postgresql.dialect())
        numeric = getattr(implementation, "impl", implementation)
        assert isinstance(numeric, Numeric)
        assert (numeric.precision, numeric.scale) == (38, 6)
    assert InstrumentDailyTradeStatistic.__table__.c.fetched_at.type.timezone


@pytest.mark.parametrize("field", [
    name for name in TRADE_STATISTIC_STORAGE_COLUMNS
    if name != "total_net_trade_volume"
])
def test_trade_statistics_model_rejects_negative_gross_values(database, field):
    session, instrument_id = database
    session.add(InstrumentDailyTradeStatistic(**_values(
        instrument_id, **{field: Decimal("-0.000001")}
    )))
    with pytest.raises(IntegrityError):
        session.commit()


def test_trade_statistics_model_rejects_nonpositive_schema(database):
    session, instrument_id = database
    session.add(InstrumentDailyTradeStatistic(**_values(instrument_id, schema_version=0)))
    with pytest.raises(IntegrityError):
        session.commit()


def test_trade_statistics_model_rejects_duplicate_instrument_date(database):
    session, instrument_id = database
    session.add_all([
        InstrumentDailyTradeStatistic(**_values(instrument_id)),
        InstrumentDailyTradeStatistic(**_values(instrument_id, source="other")),
    ])
    with pytest.raises(IntegrityError):
        session.commit()


def test_trade_statistics_model_cascades_from_instrument(database):
    session, instrument_id = database
    session.add(InstrumentDailyTradeStatistic(**_values(instrument_id)))
    session.commit()
    session.delete(session.get(Instrument, instrument_id))
    session.commit()
    assert session.scalar(select(InstrumentDailyTradeStatistic)) is None
