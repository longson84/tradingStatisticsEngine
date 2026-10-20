"""Public stored-data contracts for US Institutional Activity."""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


InstitutionalActivityStatus = Literal[
    "available", "unknown_instrument", "unsupported_instrument",
    "missing_identifier", "no_stored_filings",
]


class InstitutionalActivityHistoryResponse(BaseModel):
    report_period: date
    holder_count: int
    total_shares: int | float


class InstitutionalActivityChangeResponse(BaseModel):
    manager_id: int
    manager_name: str
    is_curated: bool
    action: Literal["new", "added", "unchanged", "reduced", "exited"]
    previous_shares: int | float
    current_shares: int | float
    share_change: int | float
    percentage_change: int | float | None
    report_period: date
    available_at: datetime
    availability_precision: Literal["accepted_at", "filing_date_conservative"]
    source_url: str


class InstitutionalActivityHolderResponse(BaseModel):
    manager_id: int
    manager_name: str
    is_curated: bool
    shares: int | float
    report_period: date
    available_at: datetime
    availability_precision: Literal["accepted_at", "filing_date_conservative"]
    source_url: str


class InstitutionalActivityResponse(BaseModel):
    status: InstitutionalActivityStatus
    message: str | None
    instrument_id: int
    symbol: str | None
    instrument_type: str | None
    venue_code: str | None
    formula_version: str
    latest_report_period: date | None
    latest_available_at: datetime | None
    action_counts: dict[str, int]
    history: list[InstitutionalActivityHistoryResponse]
    changes: list[InstitutionalActivityChangeResponse]
    current_holders: list[InstitutionalActivityHolderResponse]
