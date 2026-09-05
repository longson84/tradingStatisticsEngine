"""SQLAlchemy persistence for Data Operations batch plans."""
from __future__ import annotations

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session, selectinload

from api.db.models import DataOperationBatchPlan, DataOperationBatchStep
from api.repositories.batch_operation_repository import (
    BatchOperationPlanRecord,
    BatchOperationStepRecord,
)


class SqlAlchemyBatchOperationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_plans(self) -> tuple[BatchOperationPlanRecord, ...]:
        rows = self._session.scalars(
            select(DataOperationBatchPlan)
            .options(selectinload(DataOperationBatchPlan.steps))
            .order_by(DataOperationBatchPlan.name, DataOperationBatchPlan.id)
        ).all()
        return tuple(self._record(row) for row in rows)

    def get_plan(self, plan_id: int) -> BatchOperationPlanRecord | None:
        row = self._session.scalar(
            select(DataOperationBatchPlan)
            .where(DataOperationBatchPlan.id == plan_id)
            .options(selectinload(DataOperationBatchPlan.steps))
        )
        return self._record(row) if row is not None else None

    def name_exists(self, name: str, exclude_id: int | None = None) -> bool:
        filters = [func.lower(DataOperationBatchPlan.name) == name.casefold()]
        if exclude_id is not None:
            filters.append(DataOperationBatchPlan.id != exclude_id)
        return self._session.scalar(
            select(DataOperationBatchPlan.id).where(*filters).limit(1)
        ) is not None

    def create_plan(self, name: str, description: str) -> int:
        row = DataOperationBatchPlan(name=name, description=description)
        self._session.add(row)
        self._session.flush()
        return row.id

    def update_plan(self, plan_id: int, name: str, description: str) -> bool:
        result = self._session.execute(
            update(DataOperationBatchPlan)
            .where(DataOperationBatchPlan.id == plan_id)
            .values(name=name, description=description, updated_at=func.now())
        )
        return bool(result.rowcount)

    def replace_steps(
        self, plan_id: int, steps: tuple[BatchOperationStepRecord, ...]
    ) -> None:
        self._session.execute(
            delete(DataOperationBatchStep).where(DataOperationBatchStep.plan_id == plan_id)
        )
        self._session.add_all(
            DataOperationBatchStep(
                plan_id=plan_id,
                position=step.position,
                target_type=step.target_type,
                target_id=step.target_id,
                dataset=step.dataset,
                mode=step.mode,
            )
            for step in steps
        )
        self._session.flush()

    def delete_plan(self, plan_id: int) -> bool:
        result = self._session.execute(
            delete(DataOperationBatchPlan).where(DataOperationBatchPlan.id == plan_id)
        )
        return bool(result.rowcount)

    @staticmethod
    def _record(row: DataOperationBatchPlan) -> BatchOperationPlanRecord:
        return BatchOperationPlanRecord(
            id=row.id,
            name=row.name,
            description=row.description,
            created_at=row.created_at,
            updated_at=row.updated_at,
            steps=tuple(
                BatchOperationStepRecord(
                    position=step.position,
                    target_type=step.target_type,
                    target_id=step.target_id,
                    dataset=step.dataset,
                    mode=step.mode,
                )
                for step in sorted(row.steps, key=lambda value: value.position)
            ),
        )
