"""Public contracts for saved Data Operations batch plans and runs."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from api.schemas.data_operations import DataOperationJobResponse


class BatchOperationStepRequest(BaseModel):
    target_type: Literal["category", "universe", "watchlist", "instrument"]
    target_id: str = Field(min_length=1, max_length=64)
    dataset: Literal["prices", "fundamentals"] = "prices"
    mode: Literal["incremental", "full"] = "incremental"


class BatchOperationPlanRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    steps: list[BatchOperationStepRequest] = Field(min_length=1, max_length=20)


class BatchOperationStepResponse(BatchOperationStepRequest):
    position: int


class BatchOperationPlanResponse(BaseModel):
    id: int
    name: str
    description: str
    created_at: datetime
    updated_at: datetime
    steps: list[BatchOperationStepResponse]


class BatchOperationPlanListResponse(BaseModel):
    plans: list[BatchOperationPlanResponse]


class BatchOperationRunResponse(BaseModel):
    id: str
    plan_id: int | None
    plan_name: str
    status: Literal["queued", "running", "completed", "failed"]
    current_step: int
    total_steps: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None
    jobs: list[DataOperationJobResponse]


class BatchOperationRunListResponse(BaseModel):
    runs: list[BatchOperationRunResponse]


class BatchOperationPlanDeleteResponse(BaseModel):
    id: int
    deleted: bool
