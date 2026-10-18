from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from api.deps import get_trade_statistics_service
from api.main import app
from api.repositories.trade_statistics_repository import (
    DailyTradeStatisticRecord,
    TradeStatisticInstrumentRecord,
)
from api.services.trade_statistics_service import (
    TradeStatisticsCapabilityError,
    TradeStatisticsData,
    TradeStatisticsUnavailableError,
    UnknownTradeStatisticsInstrumentError,
)
from api.trade_statistics import TRADE_STATISTIC_STORAGE_COLUMNS
from trading_engine.types import TurnoverIntensityAnalysis, TurnoverIntensityPoint


class Service:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def get_stored_range(self, instrument_id, start, end):
        self.calls.append((instrument_id, start, end))
        if self.error:
            raise self.error
        return TradeStatisticsData(
            instrument=TradeStatisticInstrumentRecord(42, "FPT", "common_stock", "HOSE", "VND"),
            requested_start=start, requested_end=end,
            first_date=date(2026, 10, 14), last_date=date(2026, 10, 16),
            rows=tuple(DailyTradeStatisticRecord(
                instrument_id=42, trading_date=day, source=source,
                schema_version=1, fetched_at=datetime(2026, 10, 18, tzinfo=UTC),
                **({name: Decimal("10") for name in TRADE_STATISTIC_STORAGE_COLUMNS} | {
                    "market_cap": Decimal("9007199254740993"),
                    "average_buy_trade_volume": Decimal("1.25"),
                    "average_sell_trade_volume": Decimal("0.125"),
                    "total_net_trade_volume": Decimal("-3.125"),
                }),
            ) for day, source in (
                (date(2026, 10, 14), "vnstock-5.1.0-vci"),
                (date(2026, 10, 16), "later-source"),
            )),
            turnover_intensity=TurnoverIntensityAnalysis(
                formula_version="turnover_intensity_v1",
                baseline_sessions=20,
                points=(
                    TurnoverIntensityPoint(
                        session=date(2026, 10, 14), intensity=0.01,
                        baseline=None, anomaly_score=None,
                        unavailable_reason="insufficient_history",
                    ),
                    TurnoverIntensityPoint(
                        session=date(2026, 10, 16), intensity=None,
                        baseline=0.015, anomaly_score=None,
                        unavailable_reason="non_positive_market_cap",
                    ),
                ),
            ),
        )


@pytest.fixture
def client():
    service = Service()
    app.dependency_overrides[get_trade_statistics_service] = lambda: service
    with TestClient(app) as client:
        yield client, service
    app.dependency_overrides.pop(get_trade_statistics_service)


def test_route_returns_instrument_requested_range_actual_dates_order_and_row_provenance(client):
    client, service = client
    response = client.get("/instruments/42/trade-statistics?start=2026-10-13&end=2026-10-17")
    assert response.status_code == 200
    body = response.json()
    assert service.calls == [(42, date(2026, 10, 13), date(2026, 10, 17))]
    assert {key: body[key] for key in (
        "instrument_id", "symbol", "instrument_type", "venue_code", "currency",
        "requested_start", "requested_end", "first_date", "last_date", "row_count",
    )} == {
        "instrument_id": 42, "symbol": "FPT", "instrument_type": "common_stock",
        "venue_code": "HOSE", "currency": "VND", "requested_start": "2026-10-13",
        "requested_end": "2026-10-17", "first_date": "2026-10-14", "last_date": "2026-10-16",
        "row_count": 2,
    }
    assert [row["trading_date"] for row in body["rows"]] == ["2026-10-14", "2026-10-16"]
    assert [row["source"] for row in body["rows"]] == ["vnstock-5.1.0-vci", "later-source"]
    assert all(row["schema_version"] == 1 and row["fetched_at"] == "2026-10-18T00:00:00Z" for row in body["rows"])
    assert "is_complete" not in body
    assert body["turnover_intensity"] == {
        "formula_version": "turnover_intensity_v1",
        "baseline_sessions": 20,
        "points": [
            {
                "trading_date": "2026-10-14", "intensity": 0.01,
                "baseline": None, "anomaly_score": None,
                "unavailable_reason": "insufficient_history",
            },
            {
                "trading_date": "2026-10-16", "intensity": None,
                "baseline": 0.015, "anomaly_score": None,
                "unavailable_reason": "non_positive_market_cap",
            },
        ],
    }


def test_route_serializes_large_integer_exactly_and_fractional_averages_as_numbers(client):
    client, _ = client
    response = client.get("/instruments/42/trade-statistics?start=2026-10-13&end=2026-10-17")
    row = response.json()["rows"][0]
    assert type(row["market_cap"]) is int
    assert row["market_cap"] == 9007199254740993
    assert '"market_cap":9007199254740993' in response.text
    assert row["average_buy_trade_volume"] == 1.25
    assert row["average_sell_trade_volume"] == 0.125
    assert row["total_net_trade_volume"] == -3.125
    assert set(TRADE_STATISTIC_STORAGE_COLUMNS) <= row.keys()


@pytest.mark.parametrize(("error", "status", "detail"), [
    (UnknownTradeStatisticsInstrumentError("Unknown instrument: 42"), 404, "Unknown instrument: 42"),
    (TradeStatisticsCapabilityError("Instrument 42 does not support trade_history"), 422, "Instrument 42 does not support trade_history"),
    (TradeStatisticsUnavailableError("No stored daily trade statistics for instrument 42 from 2026-10-13 through 2026-10-17"), 422,
     "No stored daily trade statistics for instrument 42 from 2026-10-13 through 2026-10-17"),
    (ValueError("start date must be on or before end date"), 422, "start date must be on or before end date"),
])
def test_route_preserves_specific_error_semantics(client, error, status, detail):
    client, service = client
    service.error = error
    response = client.get("/instruments/42/trade-statistics?start=2026-10-13&end=2026-10-17")
    assert response.status_code == status
    assert response.json() == {"detail": detail}


@pytest.mark.parametrize("query", ["", "?start=2026-10-13", "?end=2026-10-17", "?start=invalid&end=2026-10-17"])
def test_route_requires_valid_explicit_dates_before_service_read(client, query):
    client, service = client
    assert client.get(f"/instruments/42/trade-statistics{query}").status_code == 422
    assert service.calls == []


def test_openapi_declares_required_dates_and_numeric_activity_contract():
    schema = app.openapi()
    operation = schema["paths"]["/instruments/{instrument_id}/trade-statistics"]["get"]
    assert operation["operationId"] == "getInstrumentTradeStatistics"
    parameters = {item["name"]: item for item in operation["parameters"]}
    assert parameters["start"]["required"] is True
    assert parameters["end"]["required"] is True
    daily = schema["components"]["schemas"]["DailyTradeStatisticResponse"]
    assert daily["properties"]["market_cap"]["anyOf"] == [{"type": "integer"}, {"type": "number"}]
    assert set(TRADE_STATISTIC_STORAGE_COLUMNS) <= set(daily["required"])
    analysis = schema["components"]["schemas"]["TurnoverIntensityAnalysisResponse"]
    assert set(analysis["required"]) == {"formula_version", "baseline_sessions", "points"}
    point = schema["components"]["schemas"]["TurnoverIntensityPointResponse"]
    assert point["properties"]["unavailable_reason"]["anyOf"][0]["enum"] == [
        "invalid_total_value", "invalid_market_cap", "non_positive_market_cap",
        "insufficient_history", "invalid_baseline_window", "zero_baseline_variance",
    ]


def test_read_route_dependency_graph_has_database_dependencies_and_no_provider():
    route = next(route for route in app.routes if getattr(route, "path", None) == "/instruments/{instrument_id}/trade-statistics")

    def calls(dependant):
        return [dependant.call, *(call for child in dependant.dependencies for call in calls(child))]

    dependencies = calls(route.dependant)
    assert get_trade_statistics_service in dependencies
    assert any(call.__name__ == "get_db_session" for call in dependencies)
    assert all("provider" not in call.__module__ and "provider" not in call.__name__.lower() for call in dependencies)
