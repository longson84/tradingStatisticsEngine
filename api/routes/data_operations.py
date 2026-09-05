"""Instrument-centered data update endpoints."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Engine

from api.batch_operation_jobs import (
    get_batch_operation_run,
    list_batch_operation_runs,
    start_batch_operation_run,
)

from api.data_operation_jobs import (
    get_active_data_operation_job,
    get_job,
    list_jobs,
    start_data_operation_job,
)
from api.deps import (
    get_batch_operation_service,
    get_data_operation_service,
    get_database_engine,
    resolve_data_operation_plan,
)
from api.schemas.batch_operations import (
    BatchOperationPlanDeleteResponse,
    BatchOperationPlanListResponse,
    BatchOperationPlanRequest,
    BatchOperationPlanResponse,
    BatchOperationRunListResponse,
    BatchOperationRunResponse,
    BatchOperationStepResponse,
)
from api.schemas.data_operations import (
    DataOperationDataset,
    DataOperationJobResponse,
    DataOperationHistoryResponse,
    DataOperationPreviewResponse,
    DataOperationRequest,
    DataOperationScopeType,
    InstrumentPriceCoveragePageResponse,
)
from api.services.data_operation_service import (
    DataOperationService,
    UnknownDataOperationScopeError,
)
from api.services.batch_operation_service import (
    BatchOperationService,
    DuplicateBatchOperationPlanError,
    UnknownBatchOperationPlanError,
)


router = APIRouter(prefix="/data-operations", tags=["data-operations"])


@router.get("/batch-plans", response_model=BatchOperationPlanListResponse, operation_id="listBatchOperationPlans")
def list_batch_plans(
    service: Annotated[BatchOperationService, Depends(get_batch_operation_service)],
) -> BatchOperationPlanListResponse:
    return BatchOperationPlanListResponse(plans=[_batch_plan_response(row) for row in service.list_plans()])


@router.post(
    "/batch-plans",
    response_model=BatchOperationPlanResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="createBatchOperationPlan",
)
def create_batch_plan(
    request: BatchOperationPlanRequest,
    service: Annotated[BatchOperationService, Depends(get_batch_operation_service)],
) -> BatchOperationPlanResponse:
    try:
        return _batch_plan_response(service.create_plan(request.name, request.description, request.steps))
    except DuplicateBatchOperationPlanError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.put("/batch-plans/{plan_id}", response_model=BatchOperationPlanResponse, operation_id="updateBatchOperationPlan")
def update_batch_plan(
    plan_id: int,
    request: BatchOperationPlanRequest,
    service: Annotated[BatchOperationService, Depends(get_batch_operation_service)],
) -> BatchOperationPlanResponse:
    try:
        return _batch_plan_response(service.update_plan(plan_id, request.name, request.description, request.steps))
    except UnknownBatchOperationPlanError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DuplicateBatchOperationPlanError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/batch-plans/{plan_id}", response_model=BatchOperationPlanDeleteResponse, operation_id="deleteBatchOperationPlan")
def delete_batch_plan(
    plan_id: int,
    service: Annotated[BatchOperationService, Depends(get_batch_operation_service)],
) -> BatchOperationPlanDeleteResponse:
    try:
        service.delete_plan(plan_id)
    except UnknownBatchOperationPlanError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return BatchOperationPlanDeleteResponse(id=plan_id, deleted=True)


@router.post(
    "/batch-plans/{plan_id}/runs",
    response_model=BatchOperationRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="startBatchOperationRun",
)
def start_batch_plan_run(
    plan_id: int,
    service: Annotated[BatchOperationService, Depends(get_batch_operation_service)],
    engine: Annotated[Engine, Depends(get_database_engine)],
) -> BatchOperationRunResponse:
    try:
        return _batch_run_response(start_batch_operation_run(
            service.get_plan(plan_id),
            engine,
            lambda scope_type, scope_id, dataset: resolve_data_operation_plan(
                engine, scope_type, scope_id, dataset
            ),
        ))
    except UnknownBatchOperationPlanError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/batch-runs", response_model=BatchOperationRunListResponse, operation_id="listBatchOperationRuns")
def list_batch_runs(
    engine: Annotated[Engine, Depends(get_database_engine)],
    limit: int = Query(default=20, ge=1, le=100),
) -> BatchOperationRunListResponse:
    return BatchOperationRunListResponse(
        runs=[_batch_run_response(row) for row in list_batch_operation_runs(engine, limit)]
    )


@router.get("/batch-runs/{run_id}", response_model=BatchOperationRunResponse, operation_id="getBatchOperationRun")
def get_batch_run(
    run_id: str,
    engine: Annotated[Engine, Depends(get_database_engine)],
) -> BatchOperationRunResponse:
    row = get_batch_operation_run(run_id, engine)
    if row is None:
        raise HTTPException(status_code=404, detail="Batch operation run not found")
    return _batch_run_response(row)


@router.get(
    "/preview",
    response_model=DataOperationPreviewResponse,
    operation_id="previewDataOperation",
)
def preview_data_operation(
    service: Annotated[DataOperationService, Depends(get_data_operation_service)],
    scope_type: DataOperationScopeType = Query(...),
    scope_id: str = Query(..., min_length=1, max_length=64),
    dataset: DataOperationDataset = Query(default="prices"),
) -> DataOperationPreviewResponse:
    try:
        preview = service.preview(scope_type, scope_id, dataset)
    except UnknownDataOperationScopeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return DataOperationPreviewResponse(**preview.__dict__)


@router.get(
    "/coverage",
    response_model=InstrumentPriceCoveragePageResponse,
    operation_id="getDataOperationPriceCoverage",
)
def get_data_operation_price_coverage(
    service: Annotated[DataOperationService, Depends(get_data_operation_service)],
    scope_type: DataOperationScopeType = Query(...),
    scope_id: str = Query(..., min_length=1, max_length=64),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    search: str = Query(default="", max_length=64),
) -> InstrumentPriceCoveragePageResponse:
    try:
        coverage = service.price_coverage(
            scope_type,
            scope_id,
            offset=offset,
            limit=limit,
            search=search,
        )
    except UnknownDataOperationScopeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    values = coverage.__dict__.copy()
    values["instruments"] = [row.__dict__ for row in coverage.instruments]
    return InstrumentPriceCoveragePageResponse(**values)


@router.post(
    "/jobs",
    response_model=DataOperationJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="startDataOperation",
)
def start_data_operation(
    request: DataOperationRequest,
    service: Annotated[DataOperationService, Depends(get_data_operation_service)],
    engine: Annotated[Engine, Depends(get_database_engine)],
) -> DataOperationJobResponse:
    try:
        plan = service.plan(
            request.scope_type, request.scope_id, request.dataset
        )
    except UnknownDataOperationScopeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not plan.can_run:
        raise HTTPException(status_code=422, detail=plan.message)
    try:
        job = start_data_operation_job(
            scope_type=plan.scope_type,
            scope_id=plan.scope_id,
            scope_name=plan.scope_name,
            dataset=request.dataset,
            mode=request.mode,
            adapter_keys=tuple(group.adapter for group in plan.groups),
            total=plan.eligible_count,
            engine=engine,
        )
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return DataOperationJobResponse(**job.to_dict())


@router.get(
    "/jobs/active",
    response_model=DataOperationJobResponse | None,
    operation_id="getActiveDataOperationJob",
)
def get_active_data_operation(
    scope_type: DataOperationScopeType = Query(...),
    scope_id: str = Query(..., min_length=1, max_length=64),
    dataset: DataOperationDataset = Query(default="prices"),
) -> DataOperationJobResponse | None:
    job = get_active_data_operation_job(scope_type, scope_id, dataset)
    return DataOperationJobResponse(**job.to_dict()) if job is not None else None


@router.get(
    "/jobs/{job_id}",
    response_model=DataOperationJobResponse,
    operation_id="getDataOperationJob",
)
def get_data_operation_job(
    job_id: str,
    engine: Annotated[Engine, Depends(get_database_engine)],
) -> DataOperationJobResponse:
    job = get_job(job_id, engine)
    if job is None:
        raise HTTPException(status_code=404, detail="Data operation job not found")
    return DataOperationJobResponse(**job.to_dict())


@router.get(
    "/history",
    response_model=DataOperationHistoryResponse,
    operation_id="getDataOperationHistory",
)
def get_data_operation_history(
    engine: Annotated[Engine, Depends(get_database_engine)],
    limit: int = Query(default=50, ge=1, le=200),
) -> DataOperationHistoryResponse:
    jobs = list_jobs(engine, limit=limit)
    return DataOperationHistoryResponse(
        runs=[DataOperationJobResponse(**job.to_dict()) for job in jobs]
    )


def _batch_plan_response(row) -> BatchOperationPlanResponse:
    return BatchOperationPlanResponse(
        id=row.id,
        name=row.name,
        description=row.description,
        created_at=row.created_at,
        updated_at=row.updated_at,
        steps=[BatchOperationStepResponse(**step.__dict__) for step in row.steps],
    )


def _batch_run_response(row) -> BatchOperationRunResponse:
    return BatchOperationRunResponse(
        id=row.id,
        plan_id=row.plan_id,
        plan_name=row.plan_name,
        status=row.status,
        current_step=row.current_step,
        total_steps=row.total_steps,
        created_at=row.created_at,
        started_at=row.started_at,
        finished_at=row.finished_at,
        error=row.error,
        jobs=[DataOperationJobResponse(**job.to_dict()) for job in row.jobs],
    )
