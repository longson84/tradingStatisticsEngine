"""Public response schemas for stored Instrument participant flows."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class InstrumentFlowPointResponse(BaseModel):
    date: date
    buy_volume: float
    buy_value: float
    sell_volume: float
    sell_value: float
    net_volume: float
    net_value: float


class InstrumentFlowResponse(BaseModel):
    instrument_id: int
    symbol: str
    instrument_type: str
    venue_code: str | None
    currency: str
    participant_type: str
    first_date: date
    last_date: date
    expected_last_session: date
    is_stale: bool
    row_count: int
    source: str
    fetched_at: datetime
    observations: list[InstrumentFlowPointResponse]
