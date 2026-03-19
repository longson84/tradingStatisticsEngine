"""Shared Pydantic types used across multiple route schemas."""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, field_validator


class DateRange(BaseModel):
    start: date
    end: date

    @field_validator("end")
    @classmethod
    def end_after_start(cls, v: date, info) -> date:
        start = info.data.get("start")
        if start and v <= start:
            raise ValueError("end must be after start")
        return v


class WeightEventSchema(BaseModel):
    date: date
    weight: float
    price: float


class TradeSchema(BaseModel):
    symbol: str
    direction: Literal["long", "short"]
    entry_date: date
    entry_price: float
    entry_weight: float
    exit_date: date | None
    exit_price: float | None
    weight_history: list[WeightEventSchema]
    return_pct: float | None
    holding_days: int | None
    mae_pct: float | None
    mfe_pct: float | None
