from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi.testclient import TestClient

from api.deps import get_institutional_activity_service
from api.main import app
from api.services.institutional_activity_service import (
    InstitutionalActivityData,
    InstitutionalActivityHistory,
    InstitutionalActivityHolder,
    InstitutionalActivityPositionChange,
)


ACCEPTED = datetime(2026, 8, 14, 16, 30, tzinfo=UTC)


class Service:
    def __init__(self):
        self.calls = []

    def get_activity(self, instrument_id, quarters=8):
        self.calls.append((instrument_id, quarters))
        return InstitutionalActivityData(
            status="available", message=None, instrument_id=42, symbol="AAPL",
            instrument_type="common_stock", venue_code="NASDAQ",
            formula_version="institutional_position_change_v1",
            latest_report_period=date(2026, 6, 30), latest_available_at=ACCEPTED,
            action_counts={"new": 0, "added": 1, "unchanged": 0, "reduced": 0, "exited": 0},
            history=(InstitutionalActivityHistory(date(2026, 6, 30), 1, Decimal("125")),),
            changes=(InstitutionalActivityPositionChange(
                manager_id=1, manager_name="Berkshire Hathaway", is_curated=True,
                action="added", previous_shares=Decimal("100"), current_shares=Decimal("125"),
                share_change=Decimal("25"), percentage_change=Decimal("25"),
                report_period=date(2026, 6, 30), available_at=ACCEPTED,
                availability_precision="accepted_at", source_url="https://www.sec.gov/filing/1",
            ),),
            current_holders=(InstitutionalActivityHolder(
                manager_id=1, manager_name="Berkshire Hathaway", is_curated=True,
                shares=Decimal("125"), report_period=date(2026, 6, 30),
                available_at=ACCEPTED, availability_precision="accepted_at",
                source_url="https://www.sec.gov/filing/1",
            ),),
        )


def test_route_serializes_stored_institutional_activity_without_provider_dependency() -> None:
    service = Service()
    app.dependency_overrides[get_institutional_activity_service] = lambda: service
    try:
        with TestClient(app) as client:
            response = client.get("/instruments/42/institutional-activity?quarters=4")
    finally:
        app.dependency_overrides.pop(get_institutional_activity_service)

    assert response.status_code == 200
    assert service.calls == [(42, 4)]
    body = response.json()
    assert body["status"] == "available"
    assert body["history"] == [{
        "report_period": "2026-06-30", "holder_count": 1, "total_shares": 125,
    }]
    assert body["changes"][0]["action"] == "added"
    assert body["changes"][0]["available_at"] == "2026-08-14T16:30:00Z"
    assert body["current_holders"][0]["shares"] == 125


def test_route_bounds_quarters_before_calling_service() -> None:
    service = Service()
    app.dependency_overrides[get_institutional_activity_service] = lambda: service
    try:
        with TestClient(app) as client:
            assert client.get("/instruments/42/institutional-activity?quarters=0").status_code == 422
            assert client.get("/instruments/42/institutional-activity?quarters=21").status_code == 422
    finally:
        app.dependency_overrides.pop(get_institutional_activity_service)
    assert service.calls == []


def test_route_dependency_graph_contains_no_provider() -> None:
    route = next(
        route for route in app.routes
        if getattr(route, "path", None) == "/instruments/{instrument_id}/institutional-activity"
    )

    def calls(dependant):
        return [dependant.call, *(call for child in dependant.dependencies for call in calls(child))]

    dependencies = calls(route.dependant)
    assert get_institutional_activity_service in dependencies
    assert any(call.__name__ == "get_db_session" for call in dependencies)
    assert all("provider" not in call.__module__ and "provider" not in call.__name__.lower() for call in dependencies)
