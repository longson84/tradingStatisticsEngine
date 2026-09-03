"""Instrument-centered data update endpoints."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Engine

from api.data_operation_jobs import (
    get_job,
    list_jobs,
    start_data_operation_job,
)
from api.deps import get_data_operation_service, get_database_engine
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


router = APIRouter(prefix="/data-operations", tags=["data-operations"])


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
) -> InstrumentPriceCoveragePageResponse:
    try:
        coverage = service.price_coverage(
            scope_type,
            scope_id,
            offset=offset,
            limit=limit,
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
