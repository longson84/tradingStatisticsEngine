"""CRUD endpoints for user-managed single-market watchlists."""
from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

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
    InvalidWatchlistCompanyError,
    UnknownWatchlistError,
    WatchlistService,
)


router = APIRouter(prefix="/watchlists", tags=["watchlists"])


@router.get("", response_model=WatchlistListResponse, operation_id="listWatchlists")
def list_watchlists(
    service: Annotated[WatchlistService, Depends(get_watchlist_service)],
    market: Literal["US", "VN"] | None = Query(default=None),
) -> WatchlistListResponse:
    return WatchlistListResponse(
        watchlists=[
            WatchlistSummaryResponse(**row.__dict__)
            for row in service.list_watchlists(market)
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
            market=request.market,
            description=request.description,
            tickers=request.tickers,
        ))
    except DuplicateWatchlistError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InvalidWatchlistCompanyError as exc:
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
            tickers=request.tickers,
        ))
    except UnknownWatchlistError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DuplicateWatchlistError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InvalidWatchlistCompanyError as exc:
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
        job = start_refresh_job(watchlist.id, watchlist.name, watchlist.market)
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
        market=row.market,
        description=row.description,
        member_count=len(row.members),
        created_at=row.created_at,
        updated_at=row.updated_at,
        members=[WatchlistMemberResponse(**member.__dict__) for member in row.members],
    )
