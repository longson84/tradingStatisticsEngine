"""Saved Data Operations batch-plan use cases."""
from __future__ import annotations

from api.repositories.batch_operation_repository import (
    BatchOperationPlanRecord,
    BatchOperationRepository,
    BatchOperationStepRecord,
)


class UnknownBatchOperationPlanError(ValueError):
    pass


class DuplicateBatchOperationPlanError(ValueError):
    pass


class BatchOperationService:
    def __init__(self, repository: BatchOperationRepository) -> None:
        self._repository = repository

    def list_plans(self) -> tuple[BatchOperationPlanRecord, ...]:
        return self._repository.list_plans()

    def get_plan(self, plan_id: int) -> BatchOperationPlanRecord:
        row = self._repository.get_plan(plan_id)
        if row is None:
            raise UnknownBatchOperationPlanError(f"Unknown batch plan: {plan_id}")
        return row

    def create_plan(self, name: str, description: str, steps) -> BatchOperationPlanRecord:
        clean_name = _name(name)
        normalized = _steps(steps)
        if self._repository.name_exists(clean_name):
            raise DuplicateBatchOperationPlanError(f"A batch plan named {clean_name!r} already exists")
        plan_id = self._repository.create_plan(clean_name, description.strip())
        self._repository.replace_steps(plan_id, normalized)
        return self.get_plan(plan_id)

    def update_plan(self, plan_id: int, name: str, description: str, steps) -> BatchOperationPlanRecord:
        self.get_plan(plan_id)
        clean_name = _name(name)
        normalized = _steps(steps)
        if self._repository.name_exists(clean_name, exclude_id=plan_id):
            raise DuplicateBatchOperationPlanError(f"A batch plan named {clean_name!r} already exists")
        if not self._repository.update_plan(plan_id, clean_name, description.strip()):
            raise UnknownBatchOperationPlanError(f"Unknown batch plan: {plan_id}")
        self._repository.replace_steps(plan_id, normalized)
        return self.get_plan(plan_id)

    def delete_plan(self, plan_id: int) -> None:
        if not self._repository.delete_plan(plan_id):
            raise UnknownBatchOperationPlanError(f"Unknown batch plan: {plan_id}")


def _name(value: str) -> str:
    result = " ".join(value.split())
    if not result:
        raise ValueError("Batch plan name is required")
    return result


def _steps(values) -> tuple[BatchOperationStepRecord, ...]:
    if not values:
        raise ValueError("A batch plan requires at least one step")
    result = []
    for position, value in enumerate(values):
        target_id = value.target_id.strip()
        if not target_id:
            raise ValueError(f"Step {position + 1} requires a target")
        if value.target_type == "category" and target_id not in {
            "equity", "crypto_spot", "reference_rate", "market_index"
        }:
            raise ValueError(f"Unsupported Instrument category: {target_id}")
        result.append(BatchOperationStepRecord(
            position=position,
            target_type=value.target_type,
            target_id=target_id,
            dataset=value.dataset,
            mode=value.mode,
        ))
    return tuple(result)
