from dataclasses import replace
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session

from api.db.models import Base, Instrument, InstrumentDailyTradeStatistic
from api.repositories.trade_statistics_repository import DailyTradeStatisticWriteRecord
from api.repositories.sqlalchemy_trade_statistics_repository import SqlAlchemyTradeStatisticsRepository


FETCHED_AT = datetime(2026, 10, 18, 8, tzinfo=UTC)


def _write(instrument_id, trading_date=date(2026, 10, 16), **overrides):
    values = dict(
        instrument_id=instrument_id, trading_date=trading_date,
        source="vnstock-5.1.0-vci", schema_version=1, fetched_at=FETCHED_AT,
        market_cap=Decimal("12345678901234567890123456789012.123456"),
        total_shares=Decimal("1000"), matched_volume=Decimal("100"),
        matched_value=Decimal("1000"), deal_volume=Decimal("20"),
        deal_value=Decimal("200"), total_volume=Decimal("120"),
        total_value=Decimal("1200"), total_buy_trade=Decimal("3"),
        total_buy_trade_volume=Decimal("50"), total_sell_trade=Decimal("4"),
        total_sell_trade_volume=Decimal("60"), total_net_trade_volume=Decimal("-10"),
        total_buy_unmatched_volume=Decimal("2"), total_sell_unmatched_volume=Decimal("3"),
        average_buy_trade_volume=Decimal("123456789012345.123456"),
        average_sell_trade_volume=Decimal("15.123456"),
    )
    return DailyTradeStatisticWriteRecord(**(values | overrides))


@pytest.fixture
def database():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        instruments = [Instrument(symbol=symbol, currency="VND", source="test")
                       for symbol in ("FPT", "VNM")]
        session.add_all(instruments)
        session.commit()
        yield session, instruments[0].id, instruments[1].id, SqlAlchemyTradeStatisticsRepository(session)
    engine.dispose()


def test_repository_reads_instrument_identity_and_unknown_instruments(database):
    session, instrument_id, _, repository = database
    instrument = repository.get_instrument(instrument_id)
    assert (instrument.instrument_id, instrument.symbol, instrument.currency) == (instrument_id, "FPT", "VND")
    assert repository.get_instrument(99999) is None
    session.get(Instrument, instrument_id).is_active = False
    session.commit()
    assert repository.get_instrument(instrument_id) is None


def test_repository_upserts_all_rows_and_reads_inclusive_ordered_instrument_range(database):
    session, instrument_id, other_id, repository = database
    assert repository.upsert_rows(iter([
        _write(instrument_id, date(2026, 10, 16)),
        _write(instrument_id, date(2026, 10, 14)),
        _write(instrument_id, date(2026, 10, 15)),
    ])) == 3
    assert repository.upsert_rows([_write(other_id)]) == 1
    session.commit()
    rows = repository.list_rows(instrument_id, date(2026, 10, 15), date(2026, 10, 16))
    assert [row.trading_date for row in rows] == [date(2026, 10, 15), date(2026, 10, 16)]
    assert all(row.instrument_id == instrument_id for row in rows)
    assert rows[0].market_cap == Decimal("12345678901234567890123456789012.123456")
    assert rows[0].average_buy_trade_volume == Decimal("123456789012345.123456")
    assert rows[0].total_net_trade_volume == Decimal("-10")
    assert rows[0].fetched_at == FETCHED_AT
    assert repository.list_rows(instrument_id, date(2026, 10, 17), date(2026, 10, 18)) == ()
    assert repository.list_rows(99999, date(2026, 10, 15), date(2026, 10, 16)) == ()
    assert repository.upsert_rows([]) == 0


def test_repository_canonical_upsert_rejects_older_and_accepts_equal_fetch_time(database):
    session, instrument_id, _, repository = database
    record = _write(instrument_id)
    repository.upsert_rows([record])
    session.commit()
    newer = replace(record, fetched_at=FETCHED_AT + timedelta(hours=1), source="newer", total_value=Decimal("2000"))
    assert repository.upsert_rows([newer]) == 1
    session.commit()
    assert repository.upsert_rows([replace(record, source="stale")]) == 0
    session.commit()
    row, = repository.list_rows(instrument_id, record.trading_date, record.trading_date)
    assert (row.source, row.total_value, row.fetched_at) == ("newer", Decimal("2000"), newer.fetched_at)
    # The same instant in another timezone must compare identically on SQLite too.
    equal = replace(newer, fetched_at=newer.fetched_at.astimezone(timezone(timedelta(hours=7))), source="equal")
    assert repository.upsert_rows([equal]) == 1
    session.commit()
    assert repository.list_rows(instrument_id, record.trading_date, record.trading_date)[0].source == "equal"
    assert session.scalar(select(func.count()).select_from(InstrumentDailyTradeStatistic)) == 1


def test_repository_leaves_transaction_commit_and_rollback_to_caller(database):
    session, instrument_id, _, repository = database
    commits = []
    event.listen(session, "after_commit", lambda session: commits.append(True))
    repository.upsert_rows([
        _write(instrument_id, date(2026, 10, 15)), _write(instrument_id),
    ])
    assert commits == []
    session.rollback()
    assert repository.list_rows(instrument_id, date(2026, 10, 15), date(2026, 10, 16)) == ()


def test_repository_reads_updated_values_even_when_orm_row_was_already_loaded(database):
    session, instrument_id, _, repository = database
    record = _write(instrument_id)
    repository.upsert_rows([record])
    session.commit()
    loaded = session.scalar(select(InstrumentDailyTradeStatistic))
    repository.upsert_rows([replace(record, total_value=Decimal("2000"))])
    row, = repository.list_rows(instrument_id, record.trading_date, record.trading_date)
    assert row.total_value == Decimal("2000")
    assert loaded is not None


@pytest.mark.parametrize("overrides", [
    {"schema_version": 0}, {"schema_version": 2}, {"schema_version": True},
    {"instrument_id": 0}, {"instrument_id": 99999}, {"source": ""}, {"source": "  "},
    {"source": "x" * 101}, {"fetched_at": datetime(2026, 10, 18)},
    {"trading_date": datetime(2026, 10, 16, tzinfo=UTC)},
    {"total_value": Decimal("-1")}, {"total_value": Decimal("NaN")},
    {"total_net_trade_volume": Decimal("Infinity")}, {"total_value": 1.5},
    {"total_value": Decimal("1.0000001")},
    {"total_value": Decimal("100000000000000000000000000000000")},
    {"total_value": Decimal("99999999999999999999999999999999.9999999")},
])
def test_repository_rejects_malformed_batch_before_any_writes(database, overrides):
    session, instrument_id, _, repository = database
    repository.upsert_rows([_write(instrument_id, total_value=Decimal("777"))])
    session.commit()
    with pytest.raises(ValueError):
        repository.upsert_rows([
            _write(instrument_id, date(2026, 10, 15)),
            replace(_write(instrument_id), **overrides),
        ])
    session.commit()
    rows = repository.list_rows(instrument_id, date(2026, 10, 15), date(2026, 10, 16))
    assert len(rows) == 1
    assert rows[0].total_value == Decimal("777")


def test_repository_rejects_mixed_instruments_and_duplicate_dates(database):
    session, instrument_id, other_id, repository = database
    for records in ([ _write(instrument_id), _write(other_id)],
                    [_write(instrument_id), _write(instrument_id)]):
        with pytest.raises(ValueError):
            repository.upsert_rows(records)
    session.commit()
    assert session.scalar(select(func.count()).select_from(InstrumentDailyTradeStatistic)) == 0


def test_repository_unknown_instrument_stores_nothing(database):
    session, _, _, repository = database
    with pytest.raises(ValueError, match="unknown instrument"):
        repository.upsert_rows([_write(99999)])
    session.commit()
    assert session.scalar(select(func.count()).select_from(InstrumentDailyTradeStatistic)) == 0


def test_repository_deleting_instrument_cascades(database):
    session, instrument_id, _, repository = database
    repository.upsert_rows([_write(instrument_id)])
    session.commit()
    session.delete(session.get(Instrument, instrument_id))
    session.commit()
    assert repository.list_rows(instrument_id, date(2026, 10, 15), date(2026, 10, 16)) == ()
