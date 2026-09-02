"""Universe Stats API contracts."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator


class UniverseStatsRequest(BaseModel):
    universe_codes: list[str] = Field(min_length=1, max_length=10)

    @field_validator("universe_codes")
    @classmethod
    def validate_codes(cls, codes: list[str]) -> list[str]:
        normalized = [code.strip().upper() for code in codes if code.strip()]
        if not normalized:
            raise ValueError("Choose at least one Universe")
        return list(dict.fromkeys(normalized))


class UniverseStatsPointResponse(BaseModel):
    date: date
    median_distance_from_high: float
    median_distance_from_low: float
    eligible_count: int
    coverage_pct: float


class UniverseInstrumentStatsResponse(BaseModel):
    instrument_id: int
    symbol: str
    last_date: date
    latest_close: float
    return_1w: float | None
    return_1m: float | None
    return_3m: float | None
    distance_from_high_200d: float | None
    high_200d_date: date | None


class UniverseStatsResultResponse(BaseModel):
    universe_code: str
    universe_name: str
    member_count: int
    instruments_with_history: int
    missing_history_count: int
    first_date: date
    last_date: date
    sources: list[str]
    fetched_at: datetime
    points: list[UniverseStatsPointResponse]
    instruments: list[UniverseInstrumentStatsResponse]


class UniverseStatsErrorResponse(BaseModel):
    universe_code: str
    message: str


class UniverseStatsResponse(BaseModel):
    formula_version: str
    window: int
    minimum_coverage_pct: float
    history_years: int
    membership_mode: str
    results: list[UniverseStatsResultResponse]
    errors: list[UniverseStatsErrorResponse]
