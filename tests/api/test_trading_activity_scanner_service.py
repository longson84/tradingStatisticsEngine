from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from api.instrument_data_routing import InstrumentRoutingMetadata
from api.repositories.data_operation_repository import (
    DataOperationInstrumentRecord,
    DataOperationScopeRecord,
)
from api.repositories.trade_statistics_repository import DailyTradeStatisticRecord
from api.services.trade_statistics_service import TradingActivityScannerService
from api.trade_statistics import TRADE_STATISTIC_STORAGE_COLUMNS


NOW = datetime(2026, 10, 19, 16, tzinfo=UTC)


def _instrument(instrument_id: int, symbol: str) -> DataOperationInstrumentRecord:
    return DataOperationInstrumentRecord(
        id=instrument_id, symbol=symbol, instrument_type="common_stock",
        company_id=instrument_id, venue_code="HOSE", price_basis="unadjusted",
        first_date=None, last_date=None, row_count=0, coverage_source=None,
        coverage_fetched_at=None, attempted_through=None, returned_through=None,
        refresh_outcome=None, primary_source=None, selected_source=None,
        refresh_detail=None, attempted_at=None, display_name=f"{symbol} Corp",
    )


def _route(instrument_id: int, symbol: str, venue: str = "HOSE") -> InstrumentRoutingMetadata:
    return InstrumentRoutingMetadata(
        instrument_id=instrument_id, canonical_symbol=symbol,
        instrument_type="common_stock", company_id=instrument_id,
        venue_code=venue, currency="VND", catalog_source="test",
        provider_symbols=(), timezone_name="Asia/Ho_Chi_Minh",
        trading_calendar_code="VN_EQUITIES", session_cutoff_time=time(15, 15),
    )


def _row(instrument_id: int, day: date, intensity: int) -> DailyTradeStatisticRecord:
    values = {name: Decimal("1") for name in TRADE_STATISTIC_STORAGE_COLUMNS}
    values.update(total_value=Decimal(intensity), market_cap=Decimal("100"))
    return DailyTradeStatisticRecord(
        instrument_id=instrument_id, trading_date=day, source="test",
        schema_version=1, fetched_at=NOW, **values,
    )


class ScopeRepository:
    def __init__(self, instruments):
        self.scope = DataOperationScopeRecord("universe", "VN100", "VN100", tuple(instruments))

    def get_scope(self, scope_type, scope_id):
        return self.scope if (scope_type, scope_id) == ("universe", "VN100") else None


class RoutingRepository:
    def __init__(self, routes):
        self.routes = tuple(routes)

    def get_instrument_routes_metadata(self, instrument_ids):
        return tuple(route for route in self.routes if route.instrument_id in instrument_ids)


class ActivityRepository:
    def __init__(self, rows):
        self.rows = tuple(rows)
        self.calls = []

    def list_recent_rows(self, instrument_ids, through, limit_per_instrument):
        self.calls.append((instrument_ids, through, limit_per_instrument))
        return tuple(row for row in self.rows if row.instrument_id in instrument_ids and row.trading_date <= through)


def test_scanner_ranks_current_members_and_separates_other_states() -> None:
    instruments = [_instrument(index, symbol) for index, symbol in enumerate(
        ("FPT", "VNM", "HPG", "VCB", "AAPL"), start=1,
    )]
    target = date(2026, 10, 19)
    history_start = target - timedelta(days=20)
    rows = []
    for instrument_id, current_intensity in ((1, 50), (2, 80)):
        rows.extend(_row(instrument_id, history_start + timedelta(days=offset), offset + 1) for offset in range(20))
        rows.append(_row(instrument_id, target, current_intensity))
    rows.extend((_row(3, target - timedelta(days=1), 30), _row(4, target, 40)))
    activity = ActivityRepository(rows)
    routes = [_route(index, symbol) for index, symbol in enumerate(
        ("FPT", "VNM", "HPG", "VCB"), start=1,
    )]
    routes.append(_route(5, "AAPL", "NASDAQ"))

    result = TradingActivityScannerService(
        ScopeRepository(instruments), activity, RoutingRepository(routes), clock=lambda: NOW,
    ).scan("universe", "VN100")

    assert result.scope_name == "VN100"
    assert result.target_session == target
    assert result.counts == {"current": 2, "stale": 1, "insufficient_history": 1, "unavailable": 1}
    by_symbol = {item.symbol: item for item in result.items}
    assert (by_symbol["VNM"].rank, by_symbol["VNM"].status) == (1, "current")
    assert (by_symbol["FPT"].rank, by_symbol["FPT"].status) == (2, "current")
    assert by_symbol["HPG"].status == "stale"
    assert by_symbol["VCB"].status == "insufficient_history"
    assert by_symbol["VCB"].unavailable_reason == "insufficient_history"
    assert by_symbol["AAPL"].status == "unavailable"
    assert by_symbol["AAPL"].unavailable_reason == "unsupported_instrument"
    assert activity.calls == [((1, 2, 3, 4), target, 21)]


def test_scanner_marks_supported_member_without_rows_unavailable() -> None:
    instrument = _instrument(1, "FPT")
    result = TradingActivityScannerService(
        ScopeRepository([instrument]), ActivityRepository([]),
        RoutingRepository([_route(1, "FPT")]), clock=lambda: NOW,
    ).scan("universe", "VN100")

    assert result.target_session is None
    assert result.counts == {"current": 0, "stale": 0, "insufficient_history": 0, "unavailable": 1}
    item, = result.items
    assert item.unavailable_reason == "no_stored_activity"


def test_scanner_keeps_valid_current_intensity_rankable_when_anomaly_is_unavailable() -> None:
    instrument = _instrument(1, "FPT")
    target = date(2026, 10, 19)
    rows = [
        _row(1, target - timedelta(days=20 - offset), 10)
        for offset in range(20)
    ]
    rows.append(_row(1, target, 20))

    result = TradingActivityScannerService(
        ScopeRepository([instrument]), ActivityRepository(rows),
        RoutingRepository([_route(1, "FPT")]), clock=lambda: NOW,
    ).scan("universe", "VN100")

    item, = result.items
    assert (item.status, item.rank, item.turnover_intensity) == ("current", 1, 0.2)
    assert item.anomaly_score is None
    assert item.unavailable_reason == "zero_baseline_variance"

