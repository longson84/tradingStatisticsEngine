from dataclasses import asdict, replace
from datetime import UTC, date, datetime, tzinfo
from decimal import Decimal
from unittest.mock import patch

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from api.db.models import Base, Instrument
from api.instrument_data_routing import InstrumentRoutingMetadata, ProviderSymbol
from api.repositories.sqlalchemy_trade_statistics_repository import SqlAlchemyTradeStatisticsRepository
from api.repositories.trade_statistics_repository import DailyTradeStatisticWriteRecord
from api.services.trade_statistics_service import (
    TradeStatisticsCapabilityError,
    TradeStatisticsService,
    TradeStatisticsUnavailableError,
    UnknownTradeStatisticsInstrumentError,
)
from api.services.trade_statistics_write_service import TradeStatisticsWriteService
from api.trade_statistics import TRADE_STATISTIC_STORAGE_COLUMNS
from api.venue_calendars import venue_calendar


FETCHED_AT = datetime(2026, 10, 18, tzinfo=UTC)


class Routing:
    def __init__(self, instrument_id, *, venue="HOSE"):
        schedule = venue_calendar("HOSE")
        self.metadata = InstrumentRoutingMetadata(
            instrument_id=instrument_id, canonical_symbol="FPT",
            instrument_type="common_stock", company_id=1, venue_code=venue,
            currency="VND", catalog_source="test",
            provider_symbols=(ProviderSymbol("listing", "FPT"),),
            timezone_name=schedule.timezone_name,
            trading_calendar_code=schedule.trading_calendar_code,
            session_cutoff_time=schedule.session_cutoff_time,
        )

    def get_instrument_route_metadata(self, instrument_id):
        return self.metadata if instrument_id == self.metadata.instrument_id else None


@pytest.fixture
def database():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        instrument = Instrument(symbol="FPT", currency="VND", source="test")
        session.add(instrument)
        session.commit()
        yield SqlAlchemyTradeStatisticsRepository(session), instrument.id, Routing(instrument.id)
    engine.dispose()


def _record(instrument_id, day):
    return DailyTradeStatisticWriteRecord(
        instrument_id=instrument_id, trading_date=day, source="vnstock-5.1.0-vci",
        schema_version=1, fetched_at=FETCHED_AT,
        **({name: Decimal("10") for name in TRADE_STATISTIC_STORAGE_COLUMNS} | {
            "market_cap": Decimal("9007199254740993"),
            "average_buy_trade_volume": Decimal("1.25"),
            "total_net_trade_volume": Decimal("-3.125"),
        }),
    )


def _frame(instrument_id):
    row = asdict(_record(instrument_id, date(2026, 10, 16)))
    return pd.DataFrame([{
        "symbol": "FPT", "trading_date": row["trading_date"],
        **{name: row[name] for name in TRADE_STATISTIC_STORAGE_COLUMNS},
        "provider_source": "vnstock-5.1.0-vci",
    }])


def test_read_service_reads_only_requested_range_in_order_and_reports_actual_partial_dates(database):
    repository, instrument_id, routing = database
    repository.upsert_rows([
        _record(instrument_id, day)
        for day in (date(2026, 10, 16), date(2026, 10, 14), date(2026, 10, 12))
    ])
    # Instantiating the provider from this database read must fail the test.
    with patch("api.providers.vietnam_market.VnstockProvider", side_effect=AssertionError("provider read")):
        result = TradeStatisticsService(repository, routing).get_stored_range(
            instrument_id, date(2026, 10, 13), date(2026, 10, 17),
        )
    assert (result.requested_start, result.requested_end) == (date(2026, 10, 13), date(2026, 10, 17))
    assert (result.first_date, result.last_date) == (date(2026, 10, 14), date(2026, 10, 16))
    assert [row.trading_date for row in result.rows] == [date(2026, 10, 14), date(2026, 10, 16)]
    assert result.instrument.symbol == "FPT"
    assert result.rows[0].market_cap == Decimal("9007199254740993")
    assert result.rows[0].average_buy_trade_volume == Decimal("1.25")


@pytest.mark.parametrize("case", ["unknown", "unsupported", "reversed", "no-data"])
def test_read_service_distinguishes_invalid_instrument_range_and_no_stored_rows(database, case):
    repository, instrument_id, routing = database
    start, end = date(2026, 10, 13), date(2026, 10, 17)
    error, match = TradeStatisticsUnavailableError, "No stored daily trade statistics"
    if case == "unknown":
        instrument_id = 999999
        error, match = UnknownTradeStatisticsInstrumentError, "Unknown instrument"
    elif case == "unsupported":
        routing.metadata = replace(routing.metadata, venue_code="NASDAQ")
        error, match = TradeStatisticsCapabilityError, "does not support trade_history"
    elif case == "reversed":
        start, end = end, start
        error, match = ValueError, "on or before"
    with pytest.raises(error, match=match):
        TradeStatisticsService(repository, routing).get_stored_range(instrument_id, start, end)


def test_write_service_projects_normalized_frame_and_preserves_provenance_and_decimals(database):
    repository, instrument_id, routing = database
    assert TradeStatisticsWriteService(repository, routing).store_rows(
        instrument_id, " fpt ", _frame(instrument_id),
        source="vnstock-5.1.0-vci", fetched_at=FETCHED_AT,
    ) == 1
    row, = repository.list_rows(instrument_id, date(2026, 10, 16), date(2026, 10, 16))
    assert row.market_cap == Decimal("9007199254740993")
    assert row.average_buy_trade_volume == Decimal("1.25")
    assert row.total_net_trade_volume == Decimal("-3.125")
    assert (row.source, row.schema_version, row.fetched_at) == ("vnstock-5.1.0-vci", 1, FETCHED_AT)


class NoOffsetTimezone(tzinfo):
    def utcoffset(self, dt):
        return None


@pytest.mark.parametrize("case", ["symbol", "row-symbol", "missing-symbol", "naive", "no-offset", "unknown", "unsupported"])
def test_write_service_rejects_identity_or_timezone_errors_before_any_write(database, case):
    repository, instrument_id, routing = database
    frame, symbol, fetched_at = _frame(instrument_id), "FPT", FETCHED_AT
    error, match = ValueError, "cannot update"
    if case == "symbol":
        symbol = "VNM"
    elif case == "row-symbol":
        frame.loc[0, "symbol"] = "VNM"
    elif case == "missing-symbol":
        frame.loc[0, "symbol"] = None
    elif case in {"naive", "no-offset"}:
        fetched_at = datetime(2026, 10, 18, tzinfo=NoOffsetTimezone() if case == "no-offset" else None)
        match = "timezone-aware"
    elif case == "unknown":
        instrument_id = 999999
        error, match = UnknownTradeStatisticsInstrumentError, "Unknown instrument"
    elif case == "unsupported":
        routing.metadata = replace(routing.metadata, venue_code="NASDAQ")
        error, match = TradeStatisticsCapabilityError, "does not support trade_history"
    with pytest.raises(error, match=match):
        TradeStatisticsWriteService(repository, routing).store_rows(
            instrument_id, symbol, frame, source="test", fetched_at=fetched_at,
        )
    assert repository.list_rows(routing.metadata.instrument_id, date(2026, 10, 1), date(2026, 10, 31)) == ()
