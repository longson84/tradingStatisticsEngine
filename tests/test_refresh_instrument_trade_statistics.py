from datetime import UTC, date, datetime, time, tzinfo
from decimal import Decimal
from types import SimpleNamespace

import pandas as pd
import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from api.db.models import Base, Company, Instrument, InstrumentSymbol, PriceBar, Venue
from api.providers.vietnam_market import ProviderDataError, VnstockProvider
from api.repositories.sqlalchemy_trade_statistics_repository import (
    SqlAlchemyTradeStatisticsRepository,
)
from scripts import refresh_instrument_trade_statistics as refresh


START, END = date(2026, 10, 12), date(2026, 10, 18)
FETCHED_AT = datetime(2026, 10, 18, 8, tzinfo=UTC)


def _frame():
    row = {
        "trading_date": "2026-10-16", "end_trading_date": "2026-10-16",
        "market_cap": "100000000000.25", "total_shares": "1000000",
        "ceiling_price": 75000, "floor_price": 65000, "reference_price": 70000,
        "open": 71000, "close": 70500, "match_price": 70500,
        "price_change": -500, "percent_price_change": -0.71,
        "high": 72000, "low": 69000, "average_price": 70500,
        "average_price_adjusted": 70500, "matched_volume": 100,
        "matched_value": "1000.25", "deal_volume": 20, "deal_value": "200.5",
        "total_volume": 120, "total_value": "1200.75", "total_buy_trade": 10,
        "total_buy_trade_volume": 50, "total_sell_trade": 12,
        "total_sell_trade_volume": 70, "reference_price_adjusted": 70000,
        "open_price_adjusted": 71000, "close_price_adjusted": 70500,
        "price_change_adjusted": -500, "percent_price_change_adjusted": -0.71,
        "highest_price_adjusted": 72000, "lowest_price_adjusted": 69000,
        "total_net_trade_volume": -20, "total_buy_unmatched_volume": 1,
        "total_sell_unmatched_volume": 2, "price_change_value": "-500 (-0.71%)",
        "average_buy_trade_volume": "788.324877791", "average_sell_trade_volume": "1243.4310509554",
    }
    # Deliberately reverse sessions: the normalizer must order the whole batch.
    return pd.DataFrame([row, row | {
        "trading_date": "2026-10-14", "end_trading_date": "2026-10-14",
    }])


@pytest.fixture
def database():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session, session.begin():
        venue = Venue(
            code="HOSE", name="HOSE", venue_type="exchange", country_code="VN",
            timezone_name="Asia/Ho_Chi_Minh", trading_calendar_code="VN_EQUITIES",
            session_cutoff_time=time(15, 15), source="test",
        )
        instrument = Instrument(
            id=1, symbol="LOCAL-FPT", currency="VND", is_active=True, source="test",
            company=Company(display_name="FPT", domicile_country_code="VN", source="test"),
            venue=venue,
        )
        instrument.symbols.append(InstrumentSymbol(
            namespace="listing", symbol="FPT", is_primary=True, source="test",
        ))
        session.add(instrument)
        session.add(PriceBar(
            instrument=instrument, trading_date=date(2026, 10, 14),
            open=1, high=3, low=1, close=2, volume=123, currency="VND",
            price_scale=1000, price_basis="canonical", source="original", fetched_at=FETCHED_AT,
        ))
    yield engine
    engine.dispose()


def _provider(monkeypatch, frame=None, callback=None):
    calls = []

    def trade_history(**kwargs):
        calls.append(kwargs)
        if callback:
            callback()
        return _frame() if frame is None else frame

    def equity(symbol):
        assert symbol == "FPT"
        return SimpleNamespace(trade_history=trade_history)

    monkeypatch.setattr("api.providers.vietnam_market._package_version", lambda package: "5.1.0")
    monkeypatch.setattr(VnstockProvider, "_market", lambda self: SimpleNamespace(equity=equity))
    return VnstockProvider(), calls


def _rows(engine):
    with Session(engine) as session:
        return SqlAlchemyTradeStatisticsRepository(session).list_rows(1, START, END)


def test_refresh_makes_one_exact_vci_request_between_short_database_scopes(database, monkeypatch):
    checked_out = []
    scope_count = []
    event.listen(database, "checkout", lambda *args: (checked_out.append(True), scope_count.append(True)))
    event.listen(database, "checkin", lambda *args: checked_out.pop())

    def provider_boundary():
        assert checked_out == []
        assert len(scope_count) == 1

    provider, calls = _provider(monkeypatch, callback=provider_boundary)
    detail = refresh.refresh_instrument_trade_statistics(
        1, START, END, engine=database, provider=provider, now=FETCHED_AT,
    )

    assert calls == [{"start": "2026-10-12", "end": "2026-10-18", "resolution": "1D", "source": "vci"}]
    assert len(scope_count) == 2
    assert detail == (
        "updated LOCAL-FPT trade statistics for 2026-10-12 through 2026-10-18: "
        "stored 2 rows; returned sessions 2026-10-14 through 2026-10-16"
    )
    rows = _rows(database)
    assert [row.trading_date for row in rows] == [date(2026, 10, 14), date(2026, 10, 16)]
    assert all((row.source, row.schema_version, row.fetched_at) == (
        "vnstock-5.1.0-vci", 1, FETCHED_AT,
    ) for row in rows)
    assert rows[0].market_cap == Decimal("100000000000.25")
    assert rows[0].total_value == Decimal("1200.75")
    assert rows[0].total_net_trade_volume == Decimal("-20")
    assert rows[0].average_buy_trade_volume == Decimal("788.324877791")
    assert rows[0].average_sell_trade_volume == Decimal("1243.4310509554")
    with Session(database) as session:
        bar, = session.scalars(select(PriceBar)).all()
        assert (bar.close, bar.volume, bar.source) == (2, 123, "original")


def test_incremental_refresh_requests_only_the_tail_after_the_latest_stored_session(database, monkeypatch):
    full_provider, _ = _provider(monkeypatch, frame=_frame().iloc[[1]])
    refresh.refresh_instrument_trade_statistics(
        1, START, date(2026, 10, 14), engine=database,
        provider=full_provider, now=FETCHED_AT,
    )
    provider, calls = _provider(monkeypatch, frame=_frame().iloc[[0]])

    detail = refresh.refresh_instrument_trade_statistics(
        1, START, END, mode="incremental", engine=database,
        provider=provider, now=FETCHED_AT,
    )

    assert calls == [{
        "start": "2026-10-15", "end": "2026-10-18",
        "resolution": "1D", "source": "vci",
    }]
    assert "incremental tail 2026-10-15 through 2026-10-18" in detail


def test_incremental_refresh_skips_provider_when_requested_period_is_current(database, monkeypatch):
    provider, calls = _provider(monkeypatch)
    refresh.refresh_instrument_trade_statistics(
        1, START, END, engine=database, provider=provider, now=FETCHED_AT,
    )
    calls.clear()

    detail = refresh.refresh_instrument_trade_statistics(
        1, START, END, mode="incremental", engine=database,
        provider=provider, now=FETCHED_AT,
    )

    assert calls == []
    assert detail == (
        "LOCAL-FPT trade statistics requested through 2026-10-18 are already "
        "covered through 2026-10-16"
    )


@pytest.mark.parametrize(
    ("period_end", "current"),
    [
        (date(2026, 10, 19), datetime(2026, 10, 19, 7, tzinfo=UTC)),
        (date(2026, 10, 30), datetime(2026, 10, 18, 8, tzinfo=UTC)),
    ],
)
def test_incremental_refresh_uses_latest_completed_venue_session(
    database, monkeypatch, period_end, current,
):
    provider, calls = _provider(monkeypatch)
    refresh.refresh_instrument_trade_statistics(
        1, START, END, engine=database, provider=provider, now=FETCHED_AT,
    )
    calls.clear()

    detail = refresh.refresh_instrument_trade_statistics(
        1, START, period_end, mode="incremental", engine=database,
        provider=provider, now=current,
    )

    assert calls == []
    assert "already covered through 2026-10-16" in detail


@pytest.mark.parametrize("case", ["unknown", "inactive", "unsupported"])
def test_refresh_resolves_exact_instrument_capability_before_provider_work(database, monkeypatch, case):
    instrument_id = 999 if case == "unknown" else 1
    if case != "unknown":
        with Session(database) as session, session.begin():
            instrument = session.get(Instrument, 1)
            if case == "inactive":
                instrument.is_active = False
            else:
                instrument.venue.code = "NASDAQ"
    monkeypatch.setattr(refresh, "VnstockProvider", lambda: pytest.fail("provider must not be constructed"))
    with pytest.raises(ValueError, match="Unknown instrument|does not support trade_history"):
        refresh.refresh_instrument_trade_statistics(instrument_id, START, END, engine=database)
    assert _rows(database) == ()


class NoOffsetTimezone(tzinfo):
    def utcoffset(self, dt):
        return None


@pytest.mark.parametrize("now", [datetime(2026, 10, 18), datetime(2026, 10, 18, tzinfo=NoOffsetTimezone())])
def test_refresh_rejects_naive_now_before_database_or_provider_work(monkeypatch, now):
    monkeypatch.setattr(refresh, "create_db_engine", lambda: pytest.fail("database must not be created"))
    with pytest.raises(ValueError, match="timezone-aware"):
        refresh.refresh_instrument_trade_statistics(1, START, END, now=now)


def test_refresh_rejects_reversed_period_before_database_work(monkeypatch):
    monkeypatch.setattr(refresh, "create_db_engine", lambda: pytest.fail("database must not be created"))
    with pytest.raises(ValueError, match="on or before"):
        refresh.refresh_instrument_trade_statistics(1, END, START)


@pytest.mark.parametrize("failure", ["provider", "malformed-row", "empty", "persistence"])
def test_refresh_preserves_prior_rows_when_response_or_atomic_write_fails(database, monkeypatch, failure):
    provider, _ = _provider(monkeypatch)
    refresh.refresh_instrument_trade_statistics(1, START, END, engine=database, provider=provider, now=FETCHED_AT)
    before = _rows(database)
    frame = _frame()
    frame["market_cap"] = "999.25"
    if failure == "malformed-row":
        frame.loc[1, "close_price_adjusted"] = float("nan")
    elif failure == "empty":
        frame = frame.iloc[:0]

    def provider_boundary():
        if failure == "provider":
            raise ProviderDataError("VCI unavailable")

    provider, _ = _provider(monkeypatch, frame, provider_boundary)

    def fail_after_write(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO instrument_daily_trade_statistics"):
            raise RuntimeError("persistence failure after SQL write")

    if failure == "persistence":
        event.listen(database, "after_cursor_execute", fail_after_write)
    try:
        with pytest.raises((ProviderDataError, RuntimeError)):
            refresh.refresh_instrument_trade_statistics(
                1, START, END, engine=database, provider=provider,
                now=FETCHED_AT.replace(minute=1),
            )
    finally:
        if failure == "persistence":
            event.remove(database, "after_cursor_execute", fail_after_write)
    assert _rows(database) == before


def test_refresh_upserts_returned_rows_and_preserves_sessions_outside_response(database, monkeypatch):
    provider, _ = _provider(monkeypatch)
    refresh.refresh_instrument_trade_statistics(1, START, END, engine=database, provider=provider, now=FETCHED_AT)
    frame = _frame().iloc[:1].copy()
    frame["market_cap"] = "999.25"
    provider, _ = _provider(monkeypatch, frame)
    refresh.refresh_instrument_trade_statistics(
        1, date(2026, 10, 16), date(2026, 10, 16),
        engine=database, provider=provider, now=FETCHED_AT.replace(minute=1),
    )
    rows = _rows(database)
    assert [row.market_cap for row in rows] == [Decimal("100000000000.25"), Decimal("999.25")]
    assert [row.fetched_at for row in rows] == [FETCHED_AT, FETCHED_AT.replace(minute=1)]
