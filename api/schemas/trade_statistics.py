"""Numeric JSON contracts for stored daily Instrument trading activity."""
from datetime import date, datetime

from pydantic import BaseModel

from trading_engine.types import TurnoverIntensityUnavailableReason


class DailyTradeStatisticResponse(BaseModel):
    trading_date: date
    source: str
    schema_version: int
    fetched_at: datetime
    market_cap: int | float
    total_shares: int | float
    matched_volume: int | float
    matched_value: int | float
    deal_volume: int | float
    deal_value: int | float
    total_volume: int | float
    total_value: int | float
    total_buy_trade: int | float
    total_buy_trade_volume: int | float
    total_sell_trade: int | float
    total_sell_trade_volume: int | float
    total_net_trade_volume: int | float
    total_buy_unmatched_volume: int | float
    total_sell_unmatched_volume: int | float
    average_buy_trade_volume: int | float
    average_sell_trade_volume: int | float


class TurnoverIntensityPointResponse(BaseModel):
    trading_date: date
    intensity: float | None
    baseline: float | None
    anomaly_score: float | None
    unavailable_reason: TurnoverIntensityUnavailableReason | None


class TurnoverIntensityAnalysisResponse(BaseModel):
    formula_version: str
    baseline_sessions: int
    points: list[TurnoverIntensityPointResponse]


class InstrumentTradeStatisticsResponse(BaseModel):
    instrument_id: int
    symbol: str
    instrument_type: str
    venue_code: str | None
    currency: str
    requested_start: date
    requested_end: date
    first_date: date
    last_date: date
    row_count: int
    rows: list[DailyTradeStatisticResponse]
    turnover_intensity: TurnoverIntensityAnalysisResponse
