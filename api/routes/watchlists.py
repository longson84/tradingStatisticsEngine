"""CRUD endpoints for user-managed instrument watchlists."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from api.deps import get_watchlist_service
from api.schemas.watchlist import (
    WatchlistCreateRequest,
    WatchlistDeleteResponse,
    WatchlistListResponse,
    WatchlistMemberResponse,
    WatchlistResponse,
    WatchlistRefreshJobResponse,
    WatchlistRefreshJobsResponse,
    WatchlistSummaryResponse,
    WatchlistUpdateRequest,
)
from api.watchlist_refresh_jobs import (
    get_active_job,
    get_job,
    list_latest_jobs,
    start_refresh_job,
)
from api.services.watchlist_service import (
    DuplicateWatchlistError,
    InvalidWatchlistInstrumentError,
    UnknownWatchlistError,
    WatchlistService,
)


router = APIRouter(prefix="/watchlists", tags=["watchlists"])


@router.get("", response_model=WatchlistListResponse, operation_id="listWatchlists")
def list_watchlists(
    service: Annotated[WatchlistService, Depends(get_watchlist_service)],
) -> WatchlistListResponse:
    return WatchlistListResponse(
        watchlists=[
            WatchlistSummaryResponse(**row.__dict__)
            for row in service.list_watchlists()
        ]
    )


@router.get(
    "/refresh-jobs",
    response_model=WatchlistRefreshJobsResponse,
    operation_id="listWatchlistRefreshJobs",
)
def list_watchlist_refresh_jobs() -> WatchlistRefreshJobsResponse:
    return WatchlistRefreshJobsResponse(
        jobs=[WatchlistRefreshJobResponse(**job.to_dict()) for job in list_latest_jobs()]
    )


@router.get(
    "/refresh-jobs/{job_id}",
    response_model=WatchlistRefreshJobResponse,
    operation_id="getWatchlistRefreshJob",
)
def get_watchlist_refresh_job(job_id: str) -> WatchlistRefreshJobResponse:
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Watchlist refresh job not found")
    return WatchlistRefreshJobResponse(**job.to_dict())


@router.get(
    "/{watchlist_id}",
    response_model=WatchlistResponse,
    operation_id="getWatchlist",
)
def get_watchlist(
    watchlist_id: int,
    service: Annotated[WatchlistService, Depends(get_watchlist_service)],
) -> WatchlistResponse:
    try:
        return _response(service.get_watchlist(watchlist_id))
    except UnknownWatchlistError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "",
    response_model=WatchlistResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="createWatchlist",
)
def create_watchlist(
    request: WatchlistCreateRequest,
    service: Annotated[WatchlistService, Depends(get_watchlist_service)],
) -> WatchlistResponse:
    try:
        return _response(service.create_watchlist(
            name=request.name,
            description=request.description,
            instrument_ids=request.instrument_ids,
        ))
    except DuplicateWatchlistError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InvalidWatchlistInstrumentError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.put(
    "/{watchlist_id}",
    response_model=WatchlistResponse,
    operation_id="updateWatchlist",
)
def update_watchlist(
    watchlist_id: int,
    request: WatchlistUpdateRequest,
    service: Annotated[WatchlistService, Depends(get_watchlist_service)],
) -> WatchlistResponse:
    try:
        return _response(service.update_watchlist(
            watchlist_id,
            name=request.name,
            description=request.description,
            instrument_ids=request.instrument_ids,
        ))
    except UnknownWatchlistError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DuplicateWatchlistError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InvalidWatchlistInstrumentError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/{watchlist_id}/refresh",
    response_model=WatchlistRefreshJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="refreshWatchlistPrices",
)
def refresh_watchlist_prices(
    watchlist_id: int,
    service: Annotated[WatchlistService, Depends(get_watchlist_service)],
) -> WatchlistRefreshJobResponse:
    try:
        watchlist = service.get_watchlist(watchlist_id)
        if watchlist.equity_refresh_adapter is None:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Automatic watchlist refresh currently requires a non-empty "
                    "watchlist containing only US equities or only VN equities"
                ),
            )
        job = start_refresh_job(
            watchlist.id, watchlist.name, watchlist.equity_refresh_adapter
        )
    except UnknownWatchlistError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return WatchlistRefreshJobResponse(**job.to_dict())


@router.delete(
    "/{watchlist_id}",
    response_model=WatchlistDeleteResponse,
    operation_id="deleteWatchlist",
)
def delete_watchlist(
    watchlist_id: int,
    service: Annotated[WatchlistService, Depends(get_watchlist_service)],
) -> WatchlistDeleteResponse:
    if get_active_job(watchlist_id) is not None:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete a watchlist while its price refresh is running",
        )
    try:
        service.delete_watchlist(watchlist_id)
    except UnknownWatchlistError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return WatchlistDeleteResponse(id=watchlist_id, deleted=True)


def _response(row) -> WatchlistResponse:
    return WatchlistResponse(
        id=row.id,
        name=row.name,
        description=row.description,
        member_count=len(row.members),
        instrument_types=list(row.instrument_types),
        equity_count=row.equity_count,
        crypto_spot_count=row.crypto_spot_count,
        reference_rate_count=row.reference_rate_count,
        price_refresh_supported=row.equity_refresh_adapter is not None,
        created_at=row.created_at,
        updated_at=row.updated_at,
        members=[WatchlistMemberResponse(**member.__dict__) for member in row.members],
    )
