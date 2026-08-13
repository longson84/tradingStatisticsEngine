"""Request/response schemas for /factors endpoints."""
from __future__ import annotations

from datetime import date
from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, Field

from trading_engine.constants import DEFAULT_QR_DAYS, DEFAULT_RARITY_ZONES

RarityFactorType: TypeAlias = Literal[
    "moving_average",
    "distance_from_ma",
    "bollinger",
    "donchian",
    "distance_from_peak",
]


# ── Rarity Analysis ──────────────────────────────────────────────────────────

class RarityRequest(BaseModel):
    instrument_id: int = Field(gt=0)
    factor_type: RarityFactorType
    period: int = 200
    ma_type: Literal["sma", "ema", "wma"] = "sma"
    std_dev: float = 2.0
    zones: list[int] = DEFAULT_RARITY_ZONES
    quick_recovery_days: int = DEFAULT_QR_DAYS
    recovery_mode: Literal["price", "factor"] = "price"


class ZoneStatsSchema(BaseModel):
    zone_pct: int
    threshold_value: float
    count: int
    qr_count: int
    qr_pct: float
    count_5y: int
    qr_5y: int
    count_10y: int
    qr_10y: int
    avg_days: float
    mmae_pct: float
    mae_by_percentile: dict[str, float]   # percentile level -> MAE value
    is_current_zone: bool


class ZoneEntrySchema(BaseModel):
    zone_pct: int
    start_date: date
    entry_price: float
    entry_factor: float
    low_price: float
    low_date: date
    low_factor: float
    mae_pct: float
    days_to_low: int
    recovery_date: date | None
    days_to_recovery: int | None
    bars_elapsed: int | None
    forward_returns: dict[str, float | None]
    is_active: bool
    is_quick_recovery: bool
    level: int
    children_count: int
    parent_zone_pct: int | None
    parent_start_date: date | None


class TimeSeriesPoint(BaseModel):
    date: str   # "YYYY-MM-DD"
    price: float
    factor: float


class RarityAnalysisResponse(BaseModel):
    instrument_id: int
    factor_name: str
    symbol: str
    instrument_type: str
    company_name: str | None = None
    venue_code: str | None = None
    venue_name: str | None = None
    base_asset: str | None = None
    quote_asset: str | None = None
    currency: str
    stats_date: date
    first_date: date
    last_date: date
    total_bars: int
    current_price: float
    current_value: float
    current_percentile: float
    current_zone: int | None
    zone_entry_date: date | None
    zone_entry_price: float | None
    sessions_in_zone: int
    max_potential_drop_pct: float
    factor_context: dict[str, Any]
    zone_stats: list[ZoneStatsSchema]
    entries: list[ZoneEntrySchema]
    time_series: list[TimeSeriesPoint]
    expected_last_session: date
    data_last_session: date
    refreshed: bool
    is_stale: bool
    refresh_warning: str | None = None
    price_source: str
    price_basis: str


# ── Predefined Multi-Symbol Rarity Tables ────────────────────────────────────

class PredefinedRarityRequest(BaseModel):
    watchlist_id: int = Field(gt=0)


class PredefinedRarityRow(BaseModel):
    instrument_id: int
    symbol: str
    first_date: date
    last_date: date
    observations: int
    reference_price: float
    p50_price: float
    current_price: float
    current_value_pct: float
    current_percentile: float
    percentiles: dict[str, float]


PredefinedRarityFactorKey: TypeAlias = Literal[
    "distance_ma50",
    "distance_ma100",
    "distance_ma150",
    "distance_ma200",
    "distance_high_100",
    "distance_high_150",
    "distance_high_200",
]


class PredefinedRarityTable(BaseModel):
    factor_key: PredefinedRarityFactorKey
    factor_name: str
    rows: list[PredefinedRarityRow]


class PredefinedRarityInstrumentStatus(BaseModel):
    instrument_id: int
    symbol: str
    instrument_type: str
    company_name: str | None = None
    venue_code: str | None = None
    venue_name: str | None = None
    base_asset: str | None = None
    quote_asset: str | None = None
    currency: str
    price_basis: str | None = None
    price_source: str | None = None
    expected_last_session: date | None = None
    data_last_session: date | None = None
    available: bool
    is_stale: bool


class PredefinedRarityResponse(BaseModel):
    watchlist_id: int
    watchlist_name: str
    requested_instruments: int
    available_instruments: int
    stale_instrument_ids: list[int]
    missing_instrument_ids: list[int]
    instruments: list[PredefinedRarityInstrumentStatus]
    percentile_columns: list[str]
    tables: list[PredefinedRarityTable]
    errors: list[str] = Field(default_factory=list)
