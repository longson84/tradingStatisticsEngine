from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pandas as pd
import pytest

from api.instrument_data_routing import InstrumentRoutingMetadata, ProviderSymbol
from api.repositories.instrument_flow_repository import (
    FlowInstrumentRecord,
    InstrumentFlowCoverageRecord,
    InstrumentFlowQuery,
    InstrumentFlowRecord,
)
from api.services.instrument_flow_service import (
    InstrumentFlowCapabilityError,
    InstrumentFlowService,
    InstrumentFlowUnavailableError,
    UnknownFlowInstrumentError,
)
from api.services.instrument_flow_write_service import InstrumentFlowWriteService
from api.venue_calendars import venue_calendar


class FlowRepositoryStub:
    def __init__(self, instruments: tuple[FlowInstrumentRecord, ...]) -> None:
        self.instruments = {row.instrument_id: row for row in instruments}
        self.rows: dict[tuple[int, str, date], InstrumentFlowRecord] = {}

    def get_instrument(self, instrument_id):
        return self.instruments.get(instrument_id)

    def upsert_observations(self, records):
        values = tuple(records)
        for row in values:
            self.rows[(row.instrument_id, row.participant_type, row.trading_date)] = (
                InstrumentFlowRecord(**row.__dict__)
            )
        return len(values)

    def get_coverage(self, instrument_id, participant_type):
        rows = [
            row for key, row in self.rows.items()
            if key[0] == instrument_id and key[1] == participant_type
        ]
        if not rows:
            return None
        return InstrumentFlowCoverageRecord(
            instrument_id=instrument_id,
            participant_type=participant_type,
            first_date=min(row.trading_date for row in rows),
            last_date=max(row.trading_date for row in rows),
            row_count=len(rows),
            source=rows[-1].source,
            fetched_at=max(row.fetched_at for row in rows),
        )

    def iter_observations(self, query: InstrumentFlowQuery):
        return tuple(sorted((
            row for key, row in self.rows.items()
            if key[0] == query.instrument_id
            and key[1] == query.participant_type
            and (query.start is None or row.trading_date >= query.start)
            and (query.end is None or row.trading_date <= query.end)
        ), key=lambda row: row.trading_date))


class RoutingRepositoryStub:
    def __init__(self, metadata: tuple[InstrumentRoutingMetadata, ...]) -> None:
        self.metadata = {row.instrument_id: row for row in metadata}

    def get_instrument_route_metadata(self, instrument_id):
        return self.metadata.get(instrument_id)


def _instrument(instrument_id=1, symbol="FPT", venue="HOSE"):
    return FlowInstrumentRecord(
        instrument_id=instrument_id,
        symbol=symbol,
        instrument_type="common_stock",
        venue_code=venue,
        currency="VND",
    )


def _metadata(
    instrument_id=1,
    symbol="FPT",
    *,
    instrument_type="common_stock",
    company_id=1,
    venue="HOSE",
    source="test",
):
    schedule = venue_calendar(venue) if venue else None
    return InstrumentRoutingMetadata(
        instrument_id=instrument_id,
        canonical_symbol=symbol,
        instrument_type=instrument_type,
        company_id=company_id,
        venue_code=venue,
        currency="VND" if venue in {"HOSE", "HNX", "UPCOM"} else "USD",
        catalog_source=source,
        provider_symbols=(ProviderSymbol("listing", symbol),),
        timezone_name=schedule.timezone_name if schedule else None,
        trading_calendar_code=schedule.trading_calendar_code if schedule else None,
        session_cutoff_time=schedule.session_cutoff_time if schedule else None,
    )


def _frame(symbol="FPT"):
    return pd.DataFrame({
        "symbol": [symbol, symbol],
        "date": [date(2026, 10, 14), date(2026, 10, 15)],
        "buy_volume": [100.0, 200.0],
        "buy_value": [1000.0, 2000.0],
        "sell_volume": [40.0, 70.0],
        "sell_value": [300.0, 500.0],
        "net_volume": [60.0, 130.0],
        "net_value": [123.0, -456.0],
        "provider_source": ["vnstock-5.1.0-vci", "vnstock-5.1.0-vci"],
    })


def test_write_service_validates_exact_symbol_and_timezone_aware_fetch_time():
    repository = FlowRepositoryStub((_instrument(),))
    routing = RoutingRepositoryStub((_metadata(),))
    service = InstrumentFlowWriteService(repository, routing)

    with pytest.raises(ValueError, match="timezone-aware"):
        service.store_observations(
            1, "foreign", _frame(), source="vnstock-5.1.0-vci",
            fetched_at=datetime(2026, 10, 18),
        )
    with pytest.raises(ValueError, match="cannot update"):
        service.store_observations(
            1, "foreign", _frame("ACB"), source="vnstock-5.1.0-vci",
            fetched_at=datetime(2026, 10, 18, tzinfo=UTC),
        )
    assert repository.rows == {}


def test_services_keep_same_symbol_instruments_separate_and_filter_inclusively():
    instruments = (_instrument(1), _instrument(2, venue="HNX"))
    repository = FlowRepositoryStub(instruments)
    routing = RoutingRepositoryStub((
        _metadata(1),
        _metadata(2, venue="HNX"),
    ))
    writer = InstrumentFlowWriteService(repository, routing)
    fetched_at = datetime(2026, 10, 18, tzinfo=UTC)
    writer.store_observations(
        2, "foreign", _frame(), source="vnstock-5.1.0-vci", fetched_at=fetched_at
    )
    reader = InstrumentFlowService(repository, routing)

    with pytest.raises(InstrumentFlowUnavailableError):
        reader.get_stored_flow(1, "foreign")
    result = reader.get_stored_flow(
        2,
        "foreign",
        start=date(2026, 10, 15),
        end=date(2026, 10, 15),
        now=datetime(2026, 10, 16, 9, tzinfo=UTC),
    )

    assert [row.trading_date for row in result.observations] == [date(2026, 10, 15)]
    assert result.instrument.instrument_id == 2
    assert result.expected_last_session == date(2026, 10, 16)
    assert result.is_stale is True
    assert result.coverage.row_count == 2
    assert result.observations[0].net_value == Decimal("-456.0")


def test_services_store_and_read_proprietary_flow_independently():
    repository = FlowRepositoryStub((_instrument(),))
    routing = RoutingRepositoryStub((_metadata(),))
    writer = InstrumentFlowWriteService(repository, routing)
    fetched_at = datetime(2026, 10, 18, tzinfo=UTC)

    writer.store_observations(
        1,
        "foreign",
        _frame(),
        source="vnstock-5.1.0-vci",
        fetched_at=fetched_at,
    )
    proprietary = _frame().assign(net_value=[10.0, 20.0])
    writer.store_observations(
        1,
        "proprietary",
        proprietary,
        source="vnstock-5.1.0-vci",
        fetched_at=fetched_at,
    )

    result = InstrumentFlowService(repository, routing).get_stored_flow(
        1,
        "proprietary",
        now=datetime(2026, 10, 16, 9, tzinfo=UTC),
    )

    assert result.participant_type == "proprietary"
    assert result.coverage.row_count == 2
    assert [row.net_value for row in result.observations] == [
        Decimal("10.0"), Decimal("20.0"),
    ]
    assert repository.get_coverage(1, "foreign").row_count == 2


@pytest.mark.parametrize(
    "metadata",
    [
        _metadata(1, venue="NASDAQ"),
        _metadata(1, symbol="SPX", instrument_type="market_index", company_id=None, venue=None),
        _metadata(1, symbol="BTCUSDT", instrument_type="spot", company_id=None, venue="BINANCE_SPOT"),
        _metadata(
            1, symbol="BTC-USD", instrument_type="reference_rate", company_id=None,
            venue=None, source="yahoo_finance",
        ),
    ],
)
def test_read_service_rejects_instruments_without_foreign_flow_capability(metadata):
    target = FlowInstrumentRecord(
        instrument_id=1,
        symbol=metadata.canonical_symbol,
        instrument_type=metadata.instrument_type,
        venue_code=metadata.venue_code,
        currency=metadata.currency,
    )
    service = InstrumentFlowService(
        FlowRepositoryStub((target,)), RoutingRepositoryStub((metadata,))
    )

    with pytest.raises(InstrumentFlowCapabilityError, match="foreign_flow"):
        service.get_stored_flow(1, "foreign")


def test_read_service_distinguishes_unknown_instrument_and_invalid_range():
    repository = FlowRepositoryStub((_instrument(),))
    routing = RoutingRepositoryStub((_metadata(),))
    service = InstrumentFlowService(repository, routing)

    with pytest.raises(UnknownFlowInstrumentError):
        service.get_stored_flow(999, "foreign")
    with pytest.raises(ValueError, match="start date"):
        service.get_stored_flow(
            1, "foreign", start=date(2026, 10, 16), end=date(2026, 10, 15)
        )
