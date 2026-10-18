from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException

from api.main import app
from api.repositories.session_statistics_repository import (
    SessionStatisticInstrumentRecord,
    SessionStatisticMetricRecord,
    SessionStatisticSnapshotRecord,
)
from api.routes.session_statistics import get_instrument_session_statistics
from api.services.session_statistics_service import (
    SessionStatisticValue,
    SessionStatisticsCapabilityError,
    SessionStatisticsData,
    SessionStatisticsUnavailableError,
    UnknownSessionStatisticsInstrumentError,
)
from api.session_statistics import SESSION_STATISTIC_METRICS


class Service:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def get_stored_snapshot(self, instrument_id, period_start, period_end):
        self.calls.append((instrument_id, period_start, period_end))
        if self.error:
            raise self.error
        return self.result


def _result():
    fetched_at = datetime(2026, 10, 18, tzinfo=UTC)
    metrics = tuple(
        SessionStatisticMetricRecord(metric.code, Decimal(index))
        for index, metric in enumerate(SESSION_STATISTIC_METRICS, 1)
    )
    snapshot = SessionStatisticSnapshotRecord(
        7, 42, date(2026, 10, 15), date(2026, 10, 16),
        "vnstock-5.1.0-vci", 1, fetched_at, metrics,
    )
    return SessionStatisticsData(
        instrument=SessionStatisticInstrumentRecord(
            42, "FPT", "common_stock", "HOSE", "VND"
        ),
        snapshot=snapshot,
        metrics=tuple(
            SessionStatisticValue(definition, metrics[index].value)
            for index, definition in enumerate(SESSION_STATISTIC_METRICS)
        ),
    )


def test_session_statistics_route_serializes_exact_period_and_metric_metadata():
    service = Service(result=_result())
    response = get_instrument_session_statistics(
        42, service, start=date(2026, 10, 15), end=date(2026, 10, 16)
    )

    assert service.calls == [(42, date(2026, 10, 15), date(2026, 10, 16))]
    assert response.symbol == "FPT"
    assert response.source == "vnstock-5.1.0-vci"
    assert response.schema_version == 1
    assert len(response.metrics) == 64
    assert response.metrics[0].code == "average_match_volume"
    assert response.metrics[0].group == "market_activity"
    assert response.metrics[0].value == 1.0


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (UnknownSessionStatisticsInstrumentError("unknown"), 404),
        (SessionStatisticsCapabilityError("unsupported"), 422),
        (SessionStatisticsUnavailableError("missing"), 422),
        (ValueError("bad range"), 422),
    ],
)
def test_session_statistics_route_maps_domain_errors(error, status):
    with pytest.raises(HTTPException) as exc_info:
        get_instrument_session_statistics(
            42, Service(error=error),
            start=date(2026, 10, 15), end=date(2026, 10, 16),
        )
    assert exc_info.value.status_code == status


def test_session_statistics_openapi_requires_both_period_dates():
    operation = app.openapi()["paths"][
        "/instruments/{instrument_id}/session-statistics"
    ]["get"]
    assert operation["operationId"] == "getInstrumentSessionStatistics"
    parameters = {item["name"]: item for item in operation["parameters"]}
    assert parameters["start"]["required"] is True
    assert parameters["end"]["required"] is True
