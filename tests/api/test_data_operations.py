from __future__ import annotations

from datetime import UTC, date, datetime, time

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from api.db.models import (
    Base,
    Company,
    Instrument,
    PriceBarCoverage,
    PriceRefreshState,
    Universe,
    UniverseMembership,
    Venue,
)
from api.main import app
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
        ("vnstock_data", (22,)),
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


def test_data_operations_openapi_exposes_preview_and_jobs():
    schema = app.openapi()
    assert schema["paths"]["/data-operations/preview"]["get"]["operationId"] == (
        "previewDataOperation"
    )
    assert schema["paths"]["/data-operations/jobs"]["post"]["operationId"] == (
        "startDataOperation"
    )
    assert schema["paths"]["/data-operations/coverage"]["get"]["operationId"] == (
        "getDataOperationPriceCoverage"
    )


def test_sqlalchemy_scope_projects_instrument_coverage_and_refresh_state():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    checked_at = datetime(2026, 8, 11, 17, tzinfo=UTC)
    with Session(engine) as session, session.begin():
        company = Company(
            display_name="Example Issuer",
            country_code="US",
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
            ticker="EXAMPLE",
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
    assert row.last_date == date(2026, 8, 10)
    assert row.row_count == 1_665
    assert row.coverage_source == "yfinance"
    assert row.attempted_through == date(2026, 8, 11)
    assert row.refresh_outcome == "checked_no_new_bar"
