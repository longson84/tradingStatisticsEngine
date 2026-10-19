from datetime import date

import pytest
from fastapi.testclient import TestClient

from api.deps import get_trading_activity_scanner_service
from api.main import app
from api.services.trade_statistics_service import (
    TradingActivityScannerData,
    TradingActivityScannerItem,
    UnknownTradingActivityScopeError,
)


class Service:
    def __init__(self):
        self.calls = []
        self.error = None

    def scan(self, scope_type, scope_id):
        self.calls.append((scope_type, scope_id))
        if self.error:
            raise self.error
        return TradingActivityScannerData(
            scope_type="universe", scope_id="VN100", scope_name="VN100 Index",
            target_session=date(2026, 10, 19),
            formula_version="turnover_intensity_v1", baseline_sessions=20,
            counts={"current": 1, "stale": 1, "insufficient_history": 0, "unavailable": 0},
            items=(
                TradingActivityScannerItem(
                    instrument_id=42, symbol="FPT", display_name="FPT Corp",
                    venue_code="HOSE", status="current", rank=1,
                    latest_session=date(2026, 10, 19), turnover_intensity=0.0125,
                    baseline=0.01, anomaly_score=2.5, unavailable_reason=None,
                ),
                TradingActivityScannerItem(
                    instrument_id=43, symbol="VNM", display_name="Vinamilk",
                    venue_code="HOSE", status="stale", rank=None,
                    latest_session=date(2026, 10, 18), turnover_intensity=0.009,
                    baseline=0.008, anomaly_score=1.0, unavailable_reason=None,
                ),
            ),
        )


@pytest.fixture
def client():
    service = Service()
    app.dependency_overrides[get_trading_activity_scanner_service] = lambda: service
    with TestClient(app) as client:
        yield client, service
    app.dependency_overrides.pop(get_trading_activity_scanner_service)


def test_scanner_route_returns_ranked_stored_collection_analysis(client):
    client, service = client
    response = client.get("/trading-activity/scanner?scope_type=universe&scope_id=VN100")

    assert response.status_code == 200
    assert service.calls == [("universe", "VN100")]
    assert response.json() == {
        "scope_type": "universe", "scope_id": "VN100", "scope_name": "VN100 Index",
        "target_session": "2026-10-19", "formula_version": "turnover_intensity_v1",
        "baseline_sessions": 20,
        "counts": {"current": 1, "stale": 1, "insufficient_history": 0, "unavailable": 0},
        "items": [
            {
                "instrument_id": 42, "symbol": "FPT", "display_name": "FPT Corp",
                "venue_code": "HOSE", "status": "current", "rank": 1,
                "latest_session": "2026-10-19", "turnover_intensity": 0.0125,
                "baseline": 0.01, "anomaly_score": 2.5, "unavailable_reason": None,
            },
            {
                "instrument_id": 43, "symbol": "VNM", "display_name": "Vinamilk",
                "venue_code": "HOSE", "status": "stale", "rank": None,
                "latest_session": "2026-10-18", "turnover_intensity": 0.009,
                "baseline": 0.008, "anomaly_score": 1.0, "unavailable_reason": None,
            },
        ],
    }


def test_scanner_route_rejects_unknown_or_invalid_scopes(client):
    client, service = client
    service.error = UnknownTradingActivityScopeError("Unknown watchlist: 999")
    response = client.get("/trading-activity/scanner?scope_type=watchlist&scope_id=999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Unknown watchlist: 999"}

    service.calls.clear()
    response = client.get("/trading-activity/scanner?scope_type=instrument&scope_id=42")
    assert response.status_code == 422
    assert service.calls == []


def test_scanner_openapi_and_dependency_graph_are_provider_free():
    schema = app.openapi()
    operation = schema["paths"]["/trading-activity/scanner"]["get"]
    assert operation["operationId"] == "scanTradingActivity"
    response_schema = schema["components"]["schemas"]["TradingActivityScannerResponse"]
    assert set(response_schema["required"]) == {
        "scope_type", "scope_id", "scope_name", "target_session",
        "formula_version", "baseline_sessions", "counts", "items",
    }

    route = next(route for route in app.routes if getattr(route, "path", None) == "/trading-activity/scanner")

    def calls(dependant):
        return [dependant.call, *(call for child in dependant.dependencies for call in calls(child))]

    dependencies = calls(route.dependant)
    assert get_trading_activity_scanner_service in dependencies
    assert any(call.__name__ == "get_db_session" for call in dependencies)
    assert all("provider" not in call.__module__ and "provider" not in call.__name__.lower() for call in dependencies)
