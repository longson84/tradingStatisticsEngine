from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException

from api.main import app
from api.repositories.instrument_flow_repository import (
    FlowInstrumentRecord,
    InstrumentFlowCoverageRecord,
    InstrumentFlowRecord,
)
from api.routes.market_flows import get_instrument_market_flows
from api.services.instrument_flow_service import (
    InstrumentFlowCapabilityError,
    InstrumentFlowData,
    InstrumentFlowUnavailableError,
    UnknownFlowInstrumentError,
)


class ServiceStub:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def get_stored_flow(self, instrument_id, participant_type, *, start, end):
        self.calls.append((instrument_id, participant_type, start, end))
        if self.error:
            raise self.error
        return self.result


def _result():
    fetched_at = datetime(2026, 10, 18, tzinfo=UTC)
    return InstrumentFlowData(
        instrument=FlowInstrumentRecord(
            instrument_id=42,
            symbol="FPT",
            instrument_type="common_stock",
            venue_code="HOSE",
            currency="VND",
        ),
        participant_type="foreign",
        coverage=InstrumentFlowCoverageRecord(
            instrument_id=42,
            participant_type="foreign",
            first_date=date(2026, 10, 14),
            last_date=date(2026, 10, 16),
            row_count=2,
            source="vnstock-5.1.0-vci",
            fetched_at=fetched_at,
        ),
        observations=(InstrumentFlowRecord(
            instrument_id=42,
            trading_date=date(2026, 10, 16),
            participant_type="foreign",
            buy_volume=Decimal("100"),
            buy_value=Decimal("1000"),
            sell_volume=Decimal("40"),
            sell_value=Decimal("300"),
            net_volume=Decimal("60"),
            net_value=Decimal("123"),
            currency="VND",
            source="vnstock-5.1.0-vci",
            fetched_at=fetched_at,
        ),),
        expected_last_session=date(2026, 10, 16),
        is_stale=False,
    )


def test_market_flow_route_serializes_stored_provenance_and_provider_net_values():
    service = ServiceStub(result=_result())

    response = get_instrument_market_flows(
        42, service, participant_type="foreign",
        start=date(2026, 10, 14), end=date(2026, 10, 16),
    )

    assert service.calls == [(42, "foreign", date(2026, 10, 14), date(2026, 10, 16))]
    assert response.symbol == "FPT"
    assert response.venue_code == "HOSE"
    assert response.source == "vnstock-5.1.0-vci"
    assert response.fetched_at == datetime(2026, 10, 18, tzinfo=UTC)
    assert response.observations[0].net_value == 123.0


@pytest.mark.parametrize(
    ("error", "status_code"),
    [
        (UnknownFlowInstrumentError("unknown"), 404),
        (InstrumentFlowCapabilityError("unsupported"), 422),
        (InstrumentFlowUnavailableError("missing"), 422),
        (ValueError("bad range"), 422),
    ],
)
def test_market_flow_route_maps_domain_errors(error, status_code):
    with pytest.raises(HTTPException) as exc_info:
        get_instrument_market_flows(
            42, ServiceStub(error=error), participant_type="foreign",
            start=None, end=None,
        )

    assert exc_info.value.status_code == status_code
    assert exc_info.value.detail == str(error)


def test_market_flow_openapi_advertises_only_foreign_participant_in_first_slice():
    operation = app.openapi()["paths"]["/instruments/{instrument_id}/market-flows"]["get"]
    assert operation["operationId"] == "getInstrumentMarketFlows"
    participant = next(
        item for item in operation["parameters"] if item["name"] == "participant_type"
    )
    assert participant["schema"]["enum"] == ["foreign"]
