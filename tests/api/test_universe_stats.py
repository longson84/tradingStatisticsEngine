from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from api.main import app
from api.repositories.data_operation_repository import (
    DataOperationInstrumentRecord,
    DataOperationScopeRecord,
)
from api.repositories.universe_stats_repository import (
    UniverseStatsCloseQuery,
    UniverseStatsCloseRecord,
)
from api.routes.universe_stats import run_universe_stats
from api.schemas.universe_stats import UniverseStatsRequest
from api.services.universe_stats_service import UniverseStatsService


def _instrument(instrument_id: int, *, rows: int = 250):
    return DataOperationInstrumentRecord(
        id=instrument_id,
        symbol=f"T{instrument_id}",
        display_name=f"Test Company {instrument_id}",
        instrument_type="common_stock",
        company_id=instrument_id,
        venue_code="NYSE",
        price_basis="adjusted",
        first_date=date(2025, 1, 1),
        last_date=date(2026, 8, 1),
        row_count=rows,
        coverage_source="test",
        coverage_fetched_at=datetime(2026, 8, 2, tzinfo=UTC),
        attempted_through=None,
        returned_through=None,
        refresh_outcome=None,
        primary_source=None,
        selected_source=None,
        refresh_detail=None,
        attempted_at=None,
    )


class _ScopeRepository:
    def get_scope(self, scope_type: str, scope_id: str):
        if scope_id != "US_TEST":
            return None
        return DataOperationScopeRecord(
            scope_type="universe",
            scope_id="US_TEST",
            name="US Test",
            instruments=(_instrument(11), _instrument(22)),
        )


class _StatsRepository:
    def __init__(self) -> None:
        self.query: UniverseStatsCloseQuery | None = None

    def iter_closes(self, query: UniverseStatsCloseQuery):
        self.query = query
        fetched_at = datetime(2026, 8, 2, tzinfo=UTC)
        dates = [date(2025, 1, 1) + timedelta(days=index) for index in range(250)]
        for instrument_id, multiplier in ((11, 1.0), (22, 2.0)):
            for index, trading_date in enumerate(dates):
                yield UniverseStatsCloseRecord(
                    instrument_id=instrument_id,
                    trading_date=trading_date,
                    close=(100.0 + index) * multiplier,
                    source="test-source",
                    fetched_at=fetched_at,
                )


def test_universe_stats_route_uses_exact_instrument_ids_and_canonical_bases():
    stats_repository = _StatsRepository()
    service = UniverseStatsService(_ScopeRepository(), stats_repository)

    response = run_universe_stats(
        UniverseStatsRequest(universe_codes=["us_test"]),
        service,
    )

    assert response.formula_version == "universe-distance-v2"
    assert response.membership_mode == "current_snapshot"
    assert response.window == 200
    assert len(response.results) == 1
    assert response.results[0].universe_code == "US_TEST"
    assert response.results[0].points[-1].eligible_count == 2
    assert [row.symbol for row in response.results[0].instruments] == ["T11", "T22"]
    assert [row.display_name for row in response.results[0].instruments] == [
        "Test Company 11",
        "Test Company 22",
    ]
    assert response.results[0].instruments[0].return_1w is not None
    assert response.results[0].instruments[0].return_1m is not None
    assert response.results[0].instruments[0].return_3m is not None
    assert response.results[0].instruments[0].distance_from_high_200d == 0.0
    assert response.results[0].instruments[0].high_200d_date == date(2025, 9, 7)
    assert stats_repository.query is not None
    assert stats_repository.query.instrument_price_bases == (
        (11, "adjusted"),
        (22, "adjusted"),
    )


def test_universe_stats_returns_per_universe_errors_without_hiding_successes():
    service = UniverseStatsService(_ScopeRepository(), _StatsRepository())

    response = run_universe_stats(
        UniverseStatsRequest(universe_codes=["US_TEST", "MISSING"]),
        service,
    )

    assert [result.universe_code for result in response.results] == ["US_TEST"]
    assert response.errors[0].universe_code == "MISSING"
    assert "Unknown Universe" in response.errors[0].message


def test_universe_stats_openapi_contract_is_generated_for_frontend():
    schema = app.openapi()
    operation = schema["paths"]["/universe-stats/run"]["post"]
    assert operation["operationId"] == "runUniverseStats"
    properties = schema["components"]["schemas"]["UniverseStatsPointResponse"][
        "properties"
    ]
    assert {
        "median_distance_from_high",
        "median_distance_from_low",
        "eligible_count",
        "coverage_pct",
    }.issubset(properties)
    instrument_properties = schema["components"]["schemas"]["UniverseInstrumentStatsResponse"][
        "properties"
    ]
    assert {
        "instrument_id",
        "symbol",
        "display_name",
        "return_1w",
        "return_1m",
        "return_3m",
        "distance_from_high_200d",
        "high_200d_date",
    }.issubset(instrument_properties)
