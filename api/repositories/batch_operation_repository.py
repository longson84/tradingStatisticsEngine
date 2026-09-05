"""Persistence-neutral contracts for saved Data Operations batch plans."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class BatchOperationStepRecord:
    position: int
    target_type: str
    target_id: str
    dataset: str
    mode: str


@dataclass(frozen=True)
class BatchOperationPlanRecord:
    id: int
    name: str
    description: str
    created_at: datetime
    updated_at: datetime
    steps: tuple[BatchOperationStepRecord, ...]


class BatchOperationRepository(Protocol):
    def list_plans(self) -> tuple[BatchOperationPlanRecord, ...]: ...
    def get_plan(self, plan_id: int) -> BatchOperationPlanRecord | None: ...
    def name_exists(self, name: str, exclude_id: int | None = None) -> bool: ...
    def create_plan(self, name: str, description: str) -> int: ...
    def update_plan(self, plan_id: int, name: str, description: str) -> bool: ...
    def replace_steps(self, plan_id: int, steps: tuple[BatchOperationStepRecord, ...]) -> None: ...
    def delete_plan(self, plan_id: int) -> bool: ...
