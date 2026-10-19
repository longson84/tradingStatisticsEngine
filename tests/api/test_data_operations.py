from __future__ import annotations

from datetime import UTC, date, datetime, time
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from api.db.models import (
    Base,
    Company,
    Instrument,
    InstrumentDailyTradeStatistic,
    PriceBarCoverage,
    PriceRefreshState,
    Universe,
    UniverseMembership,
    Venue,
)
from api.main import app
from api.schemas.batch_operations import BatchOperationStepRequest
from api.schemas.data_operations import DataOperationRequest
from api.repositories.data_operation_repository import (
    DataOperationInstrumentRecord,
    DataOperationScopeRecord,
)
from api.repositories.sqlalchemy_data_operation_repository import (
    SqlAlchemyDataOperationRepository,
)
from api.services.data_operation_service import DataOperationService
from api.instrument_data_routing import InstrumentRoutingMetadata, ProviderSymbol
from api.venue_calendars import venue_calendar
from api.deps import get_data_operation_service
from api.trade_statistics import TRADE_STATISTIC_STORAGE_COLUMNS


class FakeRepository:
    def __init__(self, scopes: tuple[DataOperationScopeRecord, ...]) -> None:
        self.scopes = {(row.scope_type, row.scope_id): row for row in scopes}

    def get_scope(self, scope_type, scope_id):
        return self.scopes.get((scope_type, scope_id))


class FakeRoutingRepository:
    def __init__(self, scopes: tuple[DataOperationScopeRecord, ...]) -> None:
        self.instruments = {
            row.id: row for scope in scopes for row in scope.instruments
        }

    def get_instrument_routes_metadata(self, instrument_ids):
        return tuple(
            self._metadata(self.instruments[instrument_id])
            for instrument_id in instrument_ids
            if instrument_id in self.instruments
        )

    @staticmethod
    def _metadata(row):
        venue_code = row.venue_code
        schedule = venue_calendar(venue_code) if venue_code else None
        source = "yahoo_finance" if row.instrument_type == "reference_rate" else "test"
        namespace = (
            "yahoo_finance" if row.instrument_type == "reference_rate"
            else "binance_spot" if row.instrument_type == "spot"
            else "canonical"
        )
        return InstrumentRoutingMetadata(
            instrument_id=row.id,
            canonical_symbol=row.symbol,
            instrument_type=row.instrument_type,
            company_id=row.company_id,
            venue_code=venue_code,
            currency="VND" if row.venue_code in {"HOSE", "HNX", "UPCOM"} else "USD",
            catalog_source=source,
            provider_symbols=(ProviderSymbol(namespace, row.symbol),),
            timezone_name=schedule.timezone_name if schedule else None,
            trading_calendar_code=(
                schedule.trading_calendar_code if schedule else None
            ),
            session_cutoff_time=(schedule.session_cutoff_time if schedule else None),
        )


def data_operation_service(*scopes):
    values = tuple(scopes)
    return DataOperationService(
        FakeRepository(values), FakeRoutingRepository(values)
    )


def instrument(
    instrument_id: int,
    symbol: str,
    *,
    country_code: str = "US",
    instrument_type: str = "common_stock",
    company_id: int | None = 1,
    venue_code: str | None = None,
    first_date: date | None = None,
    last_date: date | None = None,
    row_count: int = 0,
    refresh_outcome: str | None = None,
    attempted_through: date | None = None,
    fundamental_fetched_at: datetime | None = None,
    proprietary_flow_last_date: date | None = None,
) -> DataOperationInstrumentRecord:
    if venue_code is None and company_id is not None:
        venue_code = "NASDAQ" if country_code == "US" else "HOSE"
    return DataOperationInstrumentRecord(
        id=instrument_id,
        symbol=symbol,
        instrument_type=instrument_type,
        company_id=company_id,
        venue_code=venue_code,
        price_basis=(
            "venue_unadjusted" if instrument_type == "spot"
            else "adjusted" if country_code == "US"
            else "provider_unspecified"
        ),
        first_date=first_date,
        last_date=last_date,
        row_count=row_count,
        coverage_source="test" if last_date is not None else None,
        coverage_fetched_at=(
            datetime(2026, 8, 11, 17, tzinfo=UTC)
            if last_date is not None else None
        ),
        attempted_through=attempted_through,
        returned_through=last_date,
        refresh_outcome=refresh_outcome,
        primary_source="test" if refresh_outcome is not None else None,
        selected_source="test" if refresh_outcome is not None else None,
        refresh_detail=None,
        attempted_at=(
            datetime(2026, 8, 11, 17, tzinfo=UTC)
            if refresh_outcome is not None else None
        ),
        fundamental_fetched_at=fundamental_fetched_at,
        proprietary_flow_last_date=proprietary_flow_last_date,
    )


def test_equity_universe_preview_reports_coverage_and_can_run():
    scope = DataOperationScopeRecord(
        scope_type="universe",
        scope_id="US500",
        name="S&P 500",
        instruments=(
            instrument(1, "MSFT", last_date=date(2099, 1, 1)),
            instrument(2, "MISSING"),
        ),
    )

    preview = data_operation_service(scope).preview(
        "universe",
        "US500",
        "prices",
        now=datetime(2026, 8, 11, 18, tzinfo=UTC),
    )

    assert preview.scope_name == "S&P 500"
    assert preview.instrument_count == 2
    assert preview.eligible_count == 2
    assert preview.current_count == 1
    assert preview.missing_count == 1
    assert preview.stale_count == 0
    assert preview.can_run is True
    assert preview.message.startswith("Ready to update 2 instruments via yfinance")


def test_binance_universe_is_planned_from_metadata():
    scope = DataOperationScopeRecord(
        scope_type="universe",
        scope_id="BINANCE_SPOT",
        name="Binance Spot",
        instruments=(instrument(
            10,
            "BTCUSDT",
            instrument_type="spot",
            company_id=None,
            venue_code="BINANCE_SPOT",
        ),),
    )

    preview = data_operation_service(scope).preview(
        "universe", "BINANCE_SPOT", "prices"
    )

    assert preview.eligible_count == 1
    assert preview.can_run is True
    assert "binance_spot" in preview.message


def test_binance_bulk_limit_is_configurable(monkeypatch):
    monkeypatch.setenv(
        "DATA_OPERATION_PRICES_BINANCE_SPOT_MAX_INSTRUMENTS", "1"
    )
    scope = DataOperationScopeRecord(
        scope_type="universe",
        scope_id="CRYPTO_CUSTOM",
        name="Crypto Custom",
        instruments=tuple(
            instrument(
                instrument_id,
                symbol,
                instrument_type="spot",
                company_id=None,
                venue_code="BINANCE_SPOT",
            )
            for instrument_id, symbol in ((10, "BTCUSDT"), (11, "ETHUSDT"))
        ),
    )

    preview = data_operation_service(scope).preview(
        "universe", "CRYPTO_CUSTOM", "prices"
    )

    assert preview.can_run is False
    assert "binance_spot 2/1" in preview.message


def test_reference_rate_instrument_price_update_is_supported():
    scope = DataOperationScopeRecord(
        scope_type="instrument",
        scope_id="20",
        name="ETH-USD",
        instruments=(instrument(
            20,
            "ETH-USD",
            instrument_type="reference_rate",
            company_id=None,
        ),),
    )

    preview = data_operation_service(scope).preview(
        "instrument", "20", "prices"
    )

    assert preview.can_run is True
    assert preview.eligible_count == 1
    assert preview.unsupported_count == 0


def test_market_index_is_an_exact_metadata_routed_price_instrument():
    scope = DataOperationScopeRecord(
        scope_type="instrument",
        scope_id="30",
        name="SPX",
        instruments=(instrument(
            30,
            "SPX",
            instrument_type="market_index",
            company_id=None,
        ),),
    )

    plan = data_operation_service(scope).plan("instrument", "30", "prices")

    assert plan.can_run is True
    assert plan.groups[0].adapter == "yfinance"
    assert plan.groups[0].instrument_ids == (30,)


def test_watchlist_fundamentals_are_planned_by_eligible_instrument():
    scope = DataOperationScopeRecord(
        scope_type="watchlist",
        scope_id="7",
        name="Candidates",
        instruments=(instrument(1, "MSFT"),),
    )

    preview = data_operation_service(scope).preview(
        "watchlist", "7", "fundamentals"
    )

    assert preview.eligible_count == 1
    assert preview.can_run is True
    assert "yfinance" in preview.message


def test_foreign_flow_supports_exact_eligible_vietnam_instrument():
    eligible = DataOperationScopeRecord(
        scope_type="instrument",
        scope_id="2",
        name="FPT",
        instruments=(instrument(2, "FPT", country_code="VN", venue_code="HOSE"),),
    )
    plan = data_operation_service(eligible).plan("instrument", "2", "foreign_flow")
    assert plan.can_run is True
    assert plan.groups[0].adapter == "vnstock"
    assert plan.groups[0].instrument_ids == (2,)

def test_foreign_flow_rejects_us_equity():
    scope = DataOperationScopeRecord(
        scope_type="instrument",
        scope_id="1",
        name="MSFT",
        instruments=(instrument(1, "MSFT"),),
    )
    preview = data_operation_service(scope).preview("instrument", "1", "foreign_flow")
    assert preview.eligible_count == 0
    assert preview.can_run is False


def test_proprietary_flow_supports_exact_eligible_vietnam_instrument():
    scope = DataOperationScopeRecord(
        scope_type="instrument",
        scope_id="2",
        name="FPT",
        instruments=(instrument(2, "FPT", country_code="VN", venue_code="HOSE"),),
    )

    plan = data_operation_service(scope).plan(
        "instrument", "2", "proprietary_flow"
    )

    assert plan.can_run is True
    assert plan.groups[0].adapter == "vnstock"
    assert plan.groups[0].instrument_ids == (2,)

def test_proprietary_flow_preview_uses_its_own_coverage():
    now = datetime(2026, 10, 16, 9, tzinfo=UTC)
    scope = DataOperationScopeRecord(
        scope_type="instrument",
        scope_id="2",
        name="FPT",
        instruments=(instrument(
            2,
            "FPT",
            country_code="VN",
            venue_code="HOSE",
            proprietary_flow_last_date=date(2026, 10, 16),
        ),),
    )

    preview = data_operation_service(scope).preview(
        "instrument", "2", "proprietary_flow", now=now
    )

    assert preview.current_count == 1
    assert preview.missing_count == 0


def test_session_stats_requires_exact_instrument_and_period():
    scope = DataOperationScopeRecord(
        scope_type="instrument",
        scope_id="2",
        name="FPT",
        instruments=(instrument(2, "FPT", country_code="VN", venue_code="HOSE"),),
    )
    plan = data_operation_service(scope).plan("instrument", "2", "session_stats")
    assert plan.can_run is True
    assert plan.groups[0].adapter == "vnstock"

    collection = DataOperationScopeRecord(
        scope_type="watchlist", scope_id="7", name="VN", instruments=scope.instruments
    )
    assert data_operation_service(collection).plan(
        "watchlist", "7", "session_stats"
    ).can_run is False


def test_session_stats_request_validates_period_and_full_mode():
    valid = DataOperationRequest(
        scope_type="instrument", scope_id="2", dataset="session_stats",
        mode="full", period_start=date(2026, 10, 15),
        period_end=date(2026, 10, 16),
    )
    assert valid.period_start == date(2026, 10, 15)

    invalid = [
        {"mode": "full"},
        {"mode": "incremental", "period_start": date(2026, 10, 15), "period_end": date(2026, 10, 16)},
        {"mode": "full", "period_start": date(2026, 10, 17), "period_end": date(2026, 10, 16)},
    ]
    for values in invalid:
        with pytest.raises(ValidationError):
            DataOperationRequest(
                scope_type="instrument", scope_id="2", dataset="session_stats",
                **values,
            )
    with pytest.raises(ValidationError):
        DataOperationRequest(
            scope_type="instrument", scope_id="2", dataset="prices",
            period_start=date(2026, 10, 15), period_end=date(2026, 10, 16),
        )
    with pytest.raises(ValidationError):
        BatchOperationStepRequest(
            target_type="instrument", target_id="2", dataset="session_stats",
            mode="full",
        )


def test_session_statistics_requests_require_one_instrument_both_ordered_dates_and_full_mode():
    dataset = "session_stats"
    valid = dict(scope_type="instrument", scope_id="2", dataset=dataset,
                 mode="full", period_start="2026-10-15", period_end="2026-10-16")
    assert DataOperationRequest(**valid).period_end == date(2026, 10, 16)
    assert DataOperationRequest(**(valid | {"period_end": "2026-10-15"})).period_end == date(2026, 10, 15)
    for overrides in (
        {"scope_type": "watchlist"}, {"scope_type": "universe"},
        {"scope_type": "category"}, {"period_start": None},
        {"period_end": None}, {"period_start": "2026-10-17"},
        {"mode": "incremental"},
    ):
        with pytest.raises(ValidationError):
            DataOperationRequest(**(valid | overrides))
    with pytest.raises(ValidationError):
        BatchOperationStepRequest(target_type="instrument", target_id="2",
                                  dataset=dataset, mode="full")


@pytest.mark.parametrize("scope_type", ["instrument", "watchlist", "universe"])
def test_trade_history_requests_allow_incremental_period_refresh_for_supported_scopes(scope_type):
    request = DataOperationRequest(
        scope_type=scope_type,
        scope_id="2",
        dataset="trade_history",
        mode="incremental",
        period_start="2026-10-15",
        period_end="2026-10-16",
    )

    assert request.period_start == date(2026, 10, 15)
    assert request.period_end == date(2026, 10, 16)


def test_trade_history_requests_reject_category_or_incomplete_period():
    valid = dict(
        scope_type="watchlist", scope_id="2", dataset="trade_history",
        mode="incremental", period_start="2026-10-15", period_end="2026-10-16",
    )
    for overrides in (
        {"scope_type": "category"}, {"period_start": None},
        {"period_end": None}, {"period_start": "2026-10-17"},
    ):
        with pytest.raises(ValidationError):
            DataOperationRequest(**(valid | overrides))


@pytest.mark.parametrize("dataset", ["prices", "fundamentals", "foreign_flow", "proprietary_flow"])
def test_non_exact_period_requests_reject_dates(dataset):
    with pytest.raises(ValidationError):
        DataOperationRequest(scope_type="instrument", scope_id="2", dataset=dataset,
                             mode="full", period_start="2026-10-15")


@pytest.mark.parametrize("scope_type", ["watchlist", "universe"])
def test_trade_history_planning_accepts_supported_collection_scopes(scope_type):
    scope = DataOperationScopeRecord(scope_type=scope_type, scope_id="7", name="VN",
                                    instruments=(
                                        instrument(2, "FPT", country_code="VN"),
                                        instrument(3, "VNM", country_code="VN"),
                                        instrument(4, "MSFT"),
                                    ))
    plan = data_operation_service(scope).plan(scope_type, "7", "trade_history")
    assert plan.can_run is True
    assert plan.eligible_count == 2
    assert plan.unsupported_count == 1
    assert plan.groups[0].instrument_ids == (2, 3)
    assert "1 unsupported" in plan.message


def test_trade_history_planning_rejects_unbounded_equity_category():
    scope = DataOperationScopeRecord(
        scope_type="category", scope_id="equity", name="All active equities",
        instruments=(instrument(2, "FPT", country_code="VN"),),
    )

    plan = data_operation_service(scope).plan("category", "equity", "trade_history")

    assert plan.can_run is False
    assert "Universe, Watchlist, or Instrument" in plan.message


@pytest.mark.parametrize("dataset", ["foreign_flow", "proprietary_flow"])
@pytest.mark.parametrize("scope_type", ["universe", "watchlist"])
def test_participant_flow_planning_accepts_supported_collection_scopes(
    dataset, scope_type,
):
    scope = DataOperationScopeRecord(
        scope_type=scope_type, scope_id="7", name="Vietnam candidates",
        instruments=(
            instrument(2, "FPT", country_code="VN"),
            instrument(3, "VNM", country_code="VN"),
            instrument(4, "MSFT"),
        ),
    )

    plan = data_operation_service(scope).plan(scope_type, "7", dataset)

    assert plan.can_run is True
    assert plan.eligible_count == 2
    assert plan.unsupported_count == 1
    assert plan.groups[0].adapter == "vnstock"
    assert plan.groups[0].instrument_ids == (2, 3)
    assert "1 unsupported" in plan.message


@pytest.mark.parametrize("dataset", ["foreign_flow", "proprietary_flow"])
def test_participant_flow_requests_and_plans_reject_unbounded_category(dataset):
    with pytest.raises(ValidationError, match="Universe, Watchlist, or Instrument"):
        DataOperationRequest(
            scope_type="category", scope_id="equity", dataset=dataset,
            mode="incremental",
        )
    scope = DataOperationScopeRecord(
        scope_type="category", scope_id="equity", name="All active equities",
        instruments=(instrument(2, "FPT", country_code="VN"),),
    )

    plan = data_operation_service(scope).plan("category", "equity", dataset)

    assert plan.can_run is False
    assert "Universe, Watchlist, or Instrument" in plan.message

    with pytest.raises(ValidationError, match="Universe, Watchlist, or Instrument"):
        BatchOperationStepRequest(
            target_type="category", target_id="equity", dataset=dataset,
            mode="incremental",
        )


@pytest.mark.parametrize("dataset", ["foreign_flow", "proprietary_flow"])
def test_participant_flow_planning_rejects_more_than_one_hundred_eligible_members(
    dataset, monkeypatch,
):
    monkeypatch.delenv(
        f"DATA_OPERATION_{dataset}_VNSTOCK_MAX_INSTRUMENTS", raising=False,
    )
    scope = DataOperationScopeRecord(
        scope_type="universe", scope_id="VNALL", name="VN All",
        instruments=tuple(
            instrument(index, f"VN{index}", country_code="VN")
            for index in range(1, 102)
        ),
    )

    plan = data_operation_service(scope).plan("universe", "VNALL", dataset)

    assert plan.can_run is False
    assert "vnstock 101/100" in plan.message


@pytest.mark.parametrize("row,eligible", [
    (instrument(2, "FPT", country_code="VN", venue_code="HOSE"), True),
    (instrument(2, "FPT", country_code="VN", venue_code="HNX"), True),
    (instrument(2, "FPT", country_code="VN", venue_code="UPCOM"), True),
    (instrument(2, "MSFT"), False),
    (instrument(2, "VN30", instrument_type="market_index", company_id=None), False),
    (instrument(2, "FPT", country_code="VN", company_id=None, venue_code="HOSE"), False),
])
def test_trade_history_planning_uses_instrument_capability(row, eligible):
    scope = DataOperationScopeRecord(scope_type="instrument", scope_id="2", name=row.symbol,
                                    instruments=(row,))
    plan = data_operation_service(scope).plan("instrument", "2", "trade_history")
    assert plan.can_run is eligible
    assert plan.eligible_count == int(eligible)
    assert plan.unsupported_count == int(not eligible)
    assert [(group.adapter, group.instrument_ids) for group in plan.groups] == (
        [("vnstock", (2,))] if eligible else []
    )


def test_trade_history_preview_counts_only_rows_in_exact_requested_range():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        schedule = venue_calendar("HOSE")
        stored = Instrument(
            symbol="FPT", currency="VND", source="test",
            company=Company(display_name="FPT", source="test"),
            venue=Venue(code="HOSE", name="HOSE", venue_type="exchange",
                        country_code="VN", source="test",
                        timezone_name=schedule.timezone_name,
                        trading_calendar_code=schedule.trading_calendar_code,
                        session_cutoff_time=schedule.session_cutoff_time),
        )
        session.add(stored)
        session.flush()
        for day in (14, 15, 16, 19):
            session.add(InstrumentDailyTradeStatistic(
                instrument_id=stored.id, trading_date=date(2026, 10, day),
                source="vnstock-5.1.0-vci", schema_version=1,
                fetched_at=datetime(2026, 10, 20, tzinfo=UTC),
                **{name: Decimal("0") for name in TRADE_STATISTIC_STORAGE_COLUMNS},
            ))
        session.commit()
        service = get_data_operation_service(session)
        preview = service.preview("instrument", str(stored.id), "trade_history",
                                  period_start=date(2026, 10, 15), period_end=date(2026, 10, 18))
        assert (preview.current_count, preview.missing_count, preview.stale_count) == (1, 0, 0)
        assert "2 stored sessions" in preview.message
        assert "per eligible instrument" in preview.message.lower()
        empty = service.preview("instrument", str(stored.id), "trade_history",
                                period_start=date(2026, 10, 17), period_end=date(2026, 10, 18))
        assert (empty.current_count, empty.missing_count, empty.stale_count) == (0, 1, 0)


def test_trade_history_collection_preview_counts_instrument_coverage_states():
    scope = DataOperationScopeRecord(
        scope_type="universe", scope_id="VN100", name="VN100",
        instruments=(
            instrument(1, "FPT", country_code="VN"),
            instrument(2, "VNM", country_code="VN"),
            instrument(3, "HPG", country_code="VN"),
            instrument(4, "MSFT"),
        ),
    )

    class TradeRows:
        def list_rows(self, instrument_id, start, end):
            dates = {
                1: (date(2026, 10, 15), date(2026, 10, 16)),
                2: (date(2026, 10, 15),),
                3: (),
            }.get(instrument_id, ())
            return tuple(SimpleNamespace(trading_date=value) for value in dates)

    service = DataOperationService(
        FakeRepository((scope,)), FakeRoutingRepository((scope,)),
        trade_statistics_repository=TradeRows(),
    )

    preview = service.preview(
        "universe", "VN100", "trade_history",
        period_start=date(2026, 10, 12), period_end=date(2026, 10, 16),
        now=datetime(2026, 10, 18, 8, tzinfo=UTC),
    )

    assert preview.eligible_count == 3
    assert preview.current_count == 1
    assert preview.stale_count == 1
    assert preview.missing_count == 1
    assert preview.unsupported_count == 1
    assert "3 stored sessions" in preview.message


def test_trade_history_service_preview_requires_both_period_dates():
    scope = DataOperationScopeRecord(
        scope_type="instrument", scope_id="2", name="FPT",
        instruments=(instrument(2, "FPT", country_code="VN"),),
    )

    with pytest.raises(ValueError, match="period_start and period_end"):
        data_operation_service(scope).preview(
            "instrument", "2", "trade_history", period_start=None, period_end=None,
        )


@pytest.mark.parametrize("dataset", ["session_stats", "trade_history", "prices"])
def test_preview_rejects_invalid_period_contract_before_planning(dataset):
    class UnusedService:
        def preview(self, *args, **kwargs):
            pytest.fail("Invalid preview reached planning")

    app.dependency_overrides[get_data_operation_service] = lambda: UnusedService()
    try:
        params = dict(scope_type="instrument", scope_id="2", dataset=dataset)
        if dataset == "prices":
            params["period_start"] = "2026-10-15"
        response = TestClient(app).get("/data-operations/preview", params=params)
        assert response.status_code == 422
    finally:
        app.dependency_overrides.pop(get_data_operation_service, None)


def test_fundamental_preview_uses_fundamental_fetch_state_not_price_dates():
    now = datetime(2026, 8, 11, 18, tzinfo=UTC)
    scope = DataOperationScopeRecord(
        scope_type="instrument",
        scope_id="1",
        name="MSFT",
        instruments=(instrument(
            1,
            "MSFT",
            last_date=date(2099, 1, 1),
            fundamental_fetched_at=now,
        ),),
    )

    preview = data_operation_service(scope).preview(
        "instrument", "1", "fundamentals", now=now
    )

    assert preview.current_count == 1
    assert preview.stale_count == 0
    assert preview.missing_count == 0


def test_mixed_watchlist_groups_exact_instruments_by_adapter():
    scope = DataOperationScopeRecord(
        scope_type="watchlist",
        scope_id="8",
        name="Mixed",
        instruments=(
            instrument(1, "MSFT"),
            instrument(
                2,
                "BTCUSDT",
                instrument_type="spot",
                company_id=None,
                venue_code="BINANCE_SPOT",
            ),
        ),
    )

    plan = data_operation_service(scope).plan("watchlist", "8", "prices")

    assert plan.can_run is True
    assert [(group.adapter, group.instrument_ids) for group in plan.groups] == [
        ("binance_spot", (2,)),
        ("yfinance", (1,)),
    ]


def test_new_universe_name_requires_no_routing_code_change():
    scope = DataOperationScopeRecord(
        scope_type="universe",
        scope_id="CUSTOM_GROWTH",
        name="Custom Growth",
        instruments=(instrument(1, "MSFT"),),
    )

    plan = data_operation_service(scope).plan(
        "universe", "CUSTOM_GROWTH", "fundamentals"
    )

    assert plan.can_run is True
    assert plan.groups[0].instrument_ids == (1,)


def test_same_symbol_on_different_venues_keeps_independent_ids():
    scope = DataOperationScopeRecord(
        scope_type="watchlist",
        scope_id="9",
        name="Venue identities",
        instruments=(
            instrument(11, "ABC", venue_code="NASDAQ"),
            instrument(22, "ABC", country_code="VN", venue_code="HOSE"),
        ),
    )

    plan = data_operation_service(scope).plan("watchlist", "9", "prices")

    assert [(group.adapter, group.instrument_ids) for group in plan.groups] == [
        ("vnstock", (22,)),
        ("yfinance", (11,)),
    ]


def test_price_coverage_is_instrument_grained_and_collection_counts_are_derived():
    scope = DataOperationScopeRecord(
        scope_type="watchlist",
        scope_id="7",
        name="Candidates",
        instruments=(
            instrument(
                1,
                "MSFT",
                first_date=date(2020, 1, 2),
                last_date=date(2026, 8, 7),
                row_count=1_660,
                refresh_outcome="checked_no_new_bar",
                attempted_through=date(2026, 8, 11),
            ),
            instrument(2, "MISSING"),
        ),
    )

    coverage = data_operation_service(scope).price_coverage(
        "watchlist",
        "7",
        now=datetime(2026, 8, 11, 22, tzinfo=UTC),
    )

    assert coverage.total == 2
    assert coverage.current_count == 0
    assert coverage.stale_count == 1
    assert coverage.missing_count == 1
    assert coverage.checked_no_new_bar_count == 1
    msft = coverage.instruments[0]
    assert msft.first_stored_session == date(2020, 1, 2)
    assert msft.last_stored_session == date(2026, 8, 7)
    assert msft.expected_session == date(2026, 8, 11)
    assert msft.expected_sessions_behind == 2
    assert msft.stored_sessions == 1_660
    assert msft.coverage_status == "stale"
    assert msft.last_attempted_through == date(2026, 8, 11)


def test_crypto_price_coverage_expects_daily_sessions_and_paginates():
    scope = DataOperationScopeRecord(
        scope_type="universe",
        scope_id="CRYPTO",
        name="Crypto",
        instruments=(
            instrument(
                10,
                "BTCUSDT",
                instrument_type="spot",
                company_id=None,
                venue_code="BINANCE_SPOT",
                last_date=date(2026, 8, 7),
            ),
            instrument(
                11,
                "ETHUSDT",
                instrument_type="spot",
                company_id=None,
                venue_code="BINANCE_SPOT",
                last_date=date(2026, 8, 10),
            ),
        ),
    )

    coverage = data_operation_service(scope).price_coverage(
        "universe",
        "CRYPTO",
        offset=1,
        limit=1,
        now=datetime(2026, 8, 11, 12, tzinfo=UTC),
    )

    assert coverage.total == 2
    assert coverage.current_count == 1
    assert coverage.stale_count == 1
    assert coverage.instruments[0].symbol == "ETHUSDT"
    assert coverage.instruments[0].expected_session == date(2026, 8, 10)
    assert coverage.instruments[0].expected_sessions_behind == 0


def test_price_coverage_filters_the_whole_scope_by_symbol_before_pagination():
    scope = DataOperationScopeRecord(
        scope_type="universe",
        scope_id="SEARCH",
        name="Search",
        instruments=(
            instrument(1, "AAPL"),
            instrument(2, "AAPD"),
            instrument(3, "MSFT"),
        ),
    )

    coverage = data_operation_service(scope).price_coverage(
        "universe",
        "SEARCH",
        search="aap",
        offset=1,
        limit=1,
    )

    assert coverage.total == 2
    assert [row.symbol for row in coverage.instruments] == ["AAPD"]
    assert coverage.missing_count == 3


def test_data_operations_openapi_exposes_preview_and_jobs():
    schema = app.openapi()
    assert schema["paths"]["/data-operations/preview"]["get"]["operationId"] == (
        "previewDataOperation"
    )
    assert schema["paths"]["/data-operations/jobs"]["post"]["operationId"] == (
        "startDataOperation"
    )
    assert schema["paths"]["/data-operations/jobs/active"]["get"]["operationId"] == (
        "getActiveDataOperationJob"
    )
    assert schema["paths"]["/data-operations/coverage"]["get"]["operationId"] == (
        "getDataOperationPriceCoverage"
    )
    assert schema["paths"]["/data-operations/history"]["get"]["operationId"] == (
        "getDataOperationHistory"
    )


def test_data_operation_run_history_is_durable_and_newest_first():
    from api.data_operation_jobs import DataOperationJob, _insert_job, list_jobs

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    first = DataOperationJob(
        id="a" * 32,
        scope_type="universe",
        scope_id="US500",
        scope_name="S&P 500",
        dataset="prices",
        mode="incremental",
        adapter_keys=("yfinance",),
        status="completed",
        current=500,
        total=500,
        succeeded=500,
        message="updated 500 instruments",
        output=("DATA_OPERATION_COMPLETE: updated 500 instruments",),
        created_at="2026-09-03T01:00:00+00:00",
        started_at="2026-09-03T01:00:01+00:00",
        finished_at="2026-09-03T01:10:00+00:00",
    )
    second = DataOperationJob(
        id="b" * 32,
        scope_type="universe",
        scope_id="US1000",
        scope_name="Russell 1000",
        dataset="prices",
        mode="full",
        adapter_keys=("yfinance",),
        status="failed",
        current=700,
        total=1000,
        succeeded=699,
        failed=1,
        message="Data update failed; existing observations were retained",
        error="one instrument failed",
        created_at="2026-09-03T02:00:00+00:00",
    )
    _insert_job(engine, first)
    _insert_job(engine, second)

    history = list_jobs(engine)

    assert [job.scope_id for job in history] == ["US1000", "US500"]
    assert history[0].failed == 1
    assert history[1].adapter_keys == ("yfinance",)


def test_sqlalchemy_scope_projects_instrument_coverage_and_refresh_state():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    checked_at = datetime(2026, 8, 11, 17, tzinfo=UTC)
    with Session(engine) as session, session.begin():
        company = Company(
            display_name="Example Issuer",
            domicile_country_code="US",
            source="test",
        )
        venue = Venue(
            code="NASDAQ",
            name="Nasdaq",
            venue_type="exchange",
            country_code="US",
            timezone_name="America/New_York",
            trading_calendar_code="US_EQUITIES",
            session_cutoff_time=time(16, 15),
            source="test",
        )
        instrument_row = Instrument(
            company=company,
            venue=venue,
            symbol="EXAMPLE",
            currency="USD",
            is_active=True,
            source="test",
        )
        universe = Universe(code="TEST", name="Test Universe", source="test")
        session.add_all([company, instrument_row, universe])
        session.flush()
        session.add_all([
            UniverseMembership(
                universe=universe,
                instrument=instrument_row,
                source="test",
            ),
            PriceBarCoverage(
                instrument=instrument_row,
                price_basis="adjusted",
                first_date=date(2020, 1, 2),
                last_date=date(2026, 8, 10),
                row_count=1_665,
                source="yfinance",
                fetched_at=checked_at,
            ),
            PriceRefreshState(
                instrument=instrument_row,
                price_basis="adjusted",
                attempted_through=date(2026, 8, 11),
                returned_through=date(2026, 8, 10),
                outcome="checked_no_new_bar",
                primary_source="yfinance",
                selected_source="yfinance",
                attempted_at=checked_at,
            ),
        ])

    with Session(engine) as session:
        scope = SqlAlchemyDataOperationRepository(session).get_scope("universe", "TEST")

    assert scope is not None
    row = scope.instruments[0]
    assert row.first_date == date(2020, 1, 2)
    assert row.display_name == "Example Issuer"
    assert row.last_date == date(2026, 8, 10)
    assert row.row_count == 1_665
    assert row.coverage_source == "yfinance"
    assert row.attempted_through == date(2026, 8, 11)
    assert row.refresh_outcome == "checked_no_new_bar"
