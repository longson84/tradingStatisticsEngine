"""Public contracts for instrument-centered data operations."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, model_validator


DataOperationScopeType = Literal["category", "universe", "watchlist", "instrument"]
DataOperationDataset = Literal[
    "prices", "fundamentals", "foreign_flow", "proprietary_flow", "session_stats"
]
DataOperationMode = Literal["incremental", "full"]


class DataOperationRequest(BaseModel):
    scope_type: DataOperationScopeType
    scope_id: str
    dataset: DataOperationDataset = "prices"
    mode: DataOperationMode = "incremental"
    period_start: date | None = None
    period_end: date | None = None

    @model_validator(mode="after")
    def validate_period(self):
        has_period = self.period_start is not None or self.period_end is not None
        if self.dataset == "session_stats":
            if self.period_start is None or self.period_end is None:
                raise ValueError("session_stats requires period_start and period_end")
            if self.period_start > self.period_end:
                raise ValueError("period_start must be on or before period_end")
            if self.mode != "full":
                raise ValueError("session_stats requires full mode")
        elif has_period:
            raise ValueError("period dates are only valid for session_stats")
        return self


class DataOperationPreviewResponse(BaseModel):
    scope_type: DataOperationScopeType
    scope_id: str
    scope_name: str
    dataset: DataOperationDataset
    instrument_count: int
    eligible_count: int
    current_count: int
    stale_count: int
    missing_count: int
    unsupported_count: int
    can_run: bool
    message: str


class InstrumentPriceCoverageResponse(BaseModel):
    instrument_id: int
    symbol: str
    instrument_type: str
    venue_code: str | None
    price_basis: str
    first_stored_session: date | None
    last_stored_session: date | None
    expected_session: date
    stored_sessions: int
    expected_sessions_behind: int | None
    coverage_status: Literal["current", "stale", "missing"]
    coverage_source: str | None
    coverage_fetched_at: datetime | None
    last_attempted_through: date | None
    last_returned_through: date | None
    refresh_outcome: Literal["current", "checked_no_new_bar", "failed"] | None
    refresh_source: str | None
    last_checked_at: datetime | None
    refresh_detail: str | None


class InstrumentPriceCoveragePageResponse(BaseModel):
    scope_type: DataOperationScopeType
    scope_id: str
    scope_name: str
    total: int
    offset: int
    limit: int
    current_count: int
    stale_count: int
    missing_count: int
    checked_no_new_bar_count: int
    failed_count: int
    instruments: list[InstrumentPriceCoverageResponse]


class DataOperationJobResponse(BaseModel):
    id: str
    scope_type: DataOperationScopeType
    scope_id: str
    scope_name: str
    dataset: DataOperationDataset
    mode: DataOperationMode
    period_start: date | None = None
    period_end: date | None = None
    adapter_keys: list[str]
    status: Literal["queued", "running", "completed", "failed"]
    current: int
    total: int
    succeeded: int
    failed: int
    message: str
    output: list[str]
    created_at: str | None
    started_at: str | None
    finished_at: str | None
    error: str | None


class DataOperationHistoryResponse(BaseModel):
    runs: list[DataOperationJobResponse]
