"""Background orchestration and durable audit for saved Data Operations batches."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock, Thread
import time
from typing import Callable, Literal
from uuid import uuid4

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from api.data_operation_jobs import DataOperationJob, get_job, start_data_operation_job
from api.db.models import DataOperationBatchRun
from api.repositories.batch_operation_repository import BatchOperationPlanRecord
from api.repositories.data_operation_repository import DataOperationScopeType
from api.services.data_operation_service import DataOperationDataset, DataOperationPlan


BatchStatus = Literal["queued", "running", "completed", "failed"]
PlanResolver = Callable[[DataOperationScopeType, str, DataOperationDataset], DataOperationPlan]


@dataclass(frozen=True)
class BatchOperationRunData:
    id: str
    plan_id: int | None
    plan_name: str
    status: BatchStatus
    current_step: int
    total_steps: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None
    jobs: tuple[DataOperationJob, ...]


_active_plan_ids: set[int] = set()
_lock = Lock()


def start_batch_operation_run(
    plan: BatchOperationPlanRecord,
    engine: Engine,
    plan_resolver: PlanResolver,
) -> BatchOperationRunData:
    with _lock:
        if plan.id in _active_plan_ids:
            raise RuntimeError(f"Batch plan {plan.name!r} is already running")
        _active_plan_ids.add(plan.id)
    run_id = uuid4().hex
    snapshot = [
        {
            "position": step.position,
            "target_type": step.target_type,
            "target_id": step.target_id,
            "dataset": step.dataset,
            "mode": step.mode,
        }
        for step in plan.steps
    ]
    try:
        with Session(engine) as session, session.begin():
            session.add(DataOperationBatchRun(
                id=run_id,
                plan_id=plan.id,
                plan_name=plan.name,
                step_snapshot=snapshot,
                child_job_ids=[],
                status="queued",
                current_step=0,
                total_steps=len(snapshot),
            ))
        Thread(
            target=_run_batch,
            args=(run_id, plan.id, snapshot, engine, plan_resolver),
            daemon=True,
        ).start()
    except Exception:
        with _lock:
            _active_plan_ids.discard(plan.id)
        raise
    result = get_batch_operation_run(run_id, engine)
    assert result is not None
    return result


def get_batch_operation_run(run_id: str, engine: Engine) -> BatchOperationRunData | None:
    with Session(engine) as session:
        row = session.get(DataOperationBatchRun, run_id)
        if row is None:
            return None
        values = _row_values(row)
    jobs = tuple(
        job for job_id in values["child_job_ids"]
        if (job := get_job(job_id, engine)) is not None
    )
    return BatchOperationRunData(jobs=jobs, **values["data"])


def list_batch_operation_runs(engine: Engine, limit: int = 20) -> tuple[BatchOperationRunData, ...]:
    with Session(engine) as session:
        ids = session.scalars(
            select(DataOperationBatchRun.id)
            .order_by(DataOperationBatchRun.created_at.desc())
            .limit(limit)
        ).all()
    return tuple(
        run for run_id in ids
        if (run := get_batch_operation_run(run_id, engine)) is not None
    )


def _run_batch(
    run_id: str,
    plan_id: int,
    steps: list[dict],
    engine: Engine,
    plan_resolver: PlanResolver,
) -> None:
    _update_run(engine, run_id, status="running", started_at=datetime.now(UTC))
    errors: list[str] = []
    try:
        for index, step in enumerate(steps, start=1):
            operation_plan = plan_resolver(
                step["target_type"], step["target_id"], step["dataset"]
            )
            if not operation_plan.can_run:
                raise RuntimeError(operation_plan.message)
            child = start_data_operation_job(
                scope_type=operation_plan.scope_type,
                scope_id=operation_plan.scope_id,
                scope_name=operation_plan.scope_name,
                dataset=step["dataset"],
                mode=step["mode"],
                adapter_keys=tuple(group.adapter for group in operation_plan.groups),
                total=operation_plan.eligible_count,
                engine=engine,
            )
            _append_child(engine, run_id, child.id, index)
            while True:
                current = get_job(child.id, engine)
                if current is None:
                    raise RuntimeError(f"Child job disappeared: {child.id}")
                if current.status in {"completed", "failed"}:
                    break
                time.sleep(0.5)
            if current.status == "failed":
                errors.append(f"{current.scope_name}: {current.error or current.message}")
        status: BatchStatus = "failed" if errors else "completed"
        _update_run(
            engine,
            run_id,
            status=status,
            current_step=len(steps),
            finished_at=datetime.now(UTC),
            error="\n".join(errors)[:4000] or None,
        )
    except Exception as exc:
        _update_run(
            engine,
            run_id,
            status="failed",
            finished_at=datetime.now(UTC),
            error=str(exc)[:4000],
        )
    finally:
        with _lock:
            _active_plan_ids.discard(plan_id)


def _append_child(engine: Engine, run_id: str, child_id: str, current_step: int) -> None:
    with Session(engine) as session, session.begin():
        row = session.get(DataOperationBatchRun, run_id)
        if row is not None:
            row.child_job_ids = [*row.child_job_ids, child_id]
            row.current_step = current_step


def _update_run(engine: Engine, run_id: str, **values) -> None:
    with Session(engine) as session, session.begin():
        row = session.get(DataOperationBatchRun, run_id)
        if row is not None:
            for key, value in values.items():
                setattr(row, key, value)


def _row_values(row: DataOperationBatchRun) -> dict:
    return {
        "child_job_ids": tuple(row.child_job_ids),
        "data": {
            "id": row.id,
            "plan_id": row.plan_id,
            "plan_name": row.plan_name,
            "status": row.status,
            "current_step": row.current_step,
            "total_steps": row.total_steps,
            "created_at": row.created_at,
            "started_at": row.started_at,
            "finished_at": row.finished_at,
            "error": row.error,
        },
    }
