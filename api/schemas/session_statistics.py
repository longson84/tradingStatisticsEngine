"""Public contracts for stored exact-period session statistics."""
from datetime import date, datetime

from pydantic import BaseModel

from api.session_statistics import (
    SessionStatisticGroup,
    SessionStatisticMetricCode,
    SessionStatisticUnit,
)


class SessionStatisticMetricResponse(BaseModel):
    code: SessionStatisticMetricCode
    group: SessionStatisticGroup
    label: str
    unit: SessionStatisticUnit
    order: int
    value: float


class InstrumentSessionStatisticsResponse(BaseModel):
    snapshot_id: int
    instrument_id: int
    symbol: str
    instrument_type: str
    venue_code: str | None
    currency: str
    period_start: date
    period_end: date
    source: str
    schema_version: int
    fetched_at: datetime
    metrics: list[SessionStatisticMetricResponse]
