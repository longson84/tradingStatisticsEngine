"""Endpoints for reading prices and maintaining saved market datasets."""
from __future__ import annotations

from typing import Annotated, Literal

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import (
    get_fundamental_service,
    get_price_history_service,
    get_price_storage_service,
)

from api.market_data_jobs import (
    clear_job_history,
    get_active_job,
    get_job,
    get_latest_job,
    start_refresh_job,
)
from api.market_data_config import SUPPORTED_UNIVERSES
from api.benchmark_history import load_cached_benchmark
from api.schemas.market_data import (
    MarketDataCacheStatus,
    MarketDataClearResponse,
    MarketDataJobResponse,
    MarketDataStatusResponse,
    SymbolPriceHistoryResponse,
    SymbolPricePointResponse,
)
from trading_engine.fundamentals import (
    fundamental_growth_over_years,
    point_in_time_fundamental,
    point_in_time_price_multiple,
    point_in_time_trailing_pe,
)
from trading_engine.factors import normalized_relative_strength
from trading_engine.types import DataLoadError
from api.services.price_history_service import (
    PriceHistoryNotFoundError,
    PriceHistoryService,
    UnknownPriceUniverseError,
)
from api.services.price_storage_service import PriceStorageService
from api.services.fundamental_service import (
    FundamentalService,
    FundamentalsNotFoundError,
)


router = APIRouter(prefix="/market-data", tags=["market-data"])
_UNIVERSES_BY_MARKET = {
    "US": ("US500", "US2000", "US100"),
    "VN": ("VN100", "VN30"),
}


def _normalize_market(market: str) -> str:
    normalized = market.upper()
    if normalized not in SUPPORTED_UNIVERSES:
        raise HTTPException(status_code=404, detail=f"Unsupported market: {market}")
    return normalized


def _cache_status(
    universe: str,
    price_storage_service: PriceStorageService,
    fundamental_service: FundamentalService,
) -> MarketDataCacheStatus:
    price_status = price_storage_service.get_status(universe)
    latest_job = get_latest_job(universe)
    fundamentals_job = get_latest_job(universe, "fundamentals")
    fundamental_status = fundamental_service.get_universe_status(universe)
    base = {
        "universe": universe,
        "exists": price_status is not None,
        "latest_job": latest_job.to_dict() if latest_job else None,
        "latest_fundamentals_job": (
            fundamentals_job.to_dict() if fundamentals_job else None
        ),
        "fundamentals_exists": fundamental_status is not None,
        "fundamentals_fetched_at": (
            fundamental_status.fetched_at.isoformat()
            if fundamental_status else None
        ),
        "fundamentals_symbol_count": (
            fundamental_status.symbol_count if fundamental_status else 0
        ),
        "fundamentals_snapshot_count": (
            fundamental_status.report_count if fundamental_status else 0
        ),
    }
    if price_status is None:
        return MarketDataCacheStatus(**base)
    errors = []
    if latest_job and latest_job.status == "failed" and latest_job.error:
        errors.append({"refresh": latest_job.error})
    return MarketDataCacheStatus(
        **base,
        fetched_at=price_status.fetched_at.isoformat(),
        first_date=price_status.first_date.isoformat(),
        last_date=price_status.last_date.isoformat(),
        symbol_count=price_status.symbol_count,
        row_count=price_status.row_count,
        source=_metadata_source(price_status.sources),
        price_basis=_display_price_basis(price_status.price_basis),
        errors=errors,
    )


@router.get("/status", response_model=MarketDataStatusResponse)
def market_data_status(
    price_storage_service: Annotated[
        PriceStorageService, Depends(get_price_storage_service)
    ],
    fundamental_service: Annotated[
        FundamentalService, Depends(get_fundamental_service)
    ],
) -> MarketDataStatusResponse:
    return MarketDataStatusResponse(
        price_storage="PostgreSQL",
        fundamentals_storage="PostgreSQL",
        markets=[
            _cache_status(universe, price_storage_service, fundamental_service)
            for universe in ("US500", "US2000", "US100", "VN100", "VN30")
        ],
    )


@router.get("/symbols/{symbol}/history", response_model=SymbolPriceHistoryResponse)
def symbol_price_history(
    symbol: str,
    price_history_service: Annotated[
        PriceHistoryService, Depends(get_price_history_service)
    ],
    fundamental_service: Annotated[
        FundamentalService, Depends(get_fundamental_service)
    ],
    universe: str = Query(...),
) -> SymbolPriceHistoryResponse:
    normalized = symbol.upper().strip()
    normalized_universe = _normalize_market(universe)
    try:
        stored = price_history_service.get_symbol_history(
            normalized_universe, normalized
        )
        prices = stored.prices
    except (PriceHistoryNotFoundError, UnknownPriceUniverseError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    fundamentals_history = None
    eps_ttm = pd.Series(index=prices.data.index, dtype=float)
    shares_outstanding = pd.Series(index=prices.data.index, dtype=float)
    trailing_pe = pd.Series(index=prices.data.index, dtype=float)
    trailing_pb = pd.Series(index=prices.data.index, dtype=float)
    provider_reported_pe = None
    provider_reported_pb = None
    provider_ratio_effective_date = None
    provider_ratio_period = None
    relative_strength_benchmark = (
        "VN30" if normalized_universe.startswith("VN") else "SPX"
    )
    relative_strength = pd.Series(index=prices.data.index, dtype=float)
    try:
        benchmark_prices, _ = load_cached_benchmark(relative_strength_benchmark)
        relative_strength = normalized_relative_strength(
            prices.data["close"], benchmark_prices.data["close"]
        )
    except DataLoadError:
        # Price History remains usable before the benchmark cache is refreshed.
        pass
    shares_growth = None
    shares_growth_5y = None
    try:
        market = "VN" if normalized_universe.startswith("VN") else "US"
        fundamentals_history = fundamental_service.get_symbol_history(
            market, normalized
        )
        snapshots = fundamentals_history.snapshots
        price_multiplier = 1000.0 if market == "VN" else 1.0
        eps_ttm = point_in_time_fundamental(
            prices.data.index,
            snapshots,
            value_column="eps_ttm",
            name="eps_ttm",
        )
        shares_outstanding = point_in_time_fundamental(
            prices.data.index,
            snapshots,
            value_column="shares_outstanding",
            name="shares_outstanding",
        )
        shares_growth = fundamental_growth_over_years(
            snapshots,
            value_column="shares_outstanding",
            as_of=prices.data.index.max(),
            years=10,
        )
        shares_growth_5y = fundamental_growth_over_years(
            snapshots,
            value_column="shares_outstanding",
            as_of=prices.data.index.max(),
            years=5,
        )
        trailing_pe = point_in_time_trailing_pe(
            prices.data["close"],
            snapshots,
            price_multiplier=price_multiplier,
        )
        trailing_pb = point_in_time_price_multiple(
            prices.data["close"],
            snapshots,
            value_column="book_value_per_share",
            name="trailing_pb",
            price_multiplier=price_multiplier,
        )
        if market == "VN":
            eligible = snapshots.loc[
                pd.to_datetime(snapshots["effective_date"], errors="coerce")
                <= prices.data.index.max()
            ].sort_values("effective_date")
            if not eligible.empty:
                latest_snapshot = eligible.iloc[-1]
                reported_pe = pd.to_numeric(latest_snapshot.get("reported_pe"), errors="coerce")
                reported_pb = pd.to_numeric(latest_snapshot.get("reported_pb"), errors="coerce")
                provider_reported_pe = (
                    float(reported_pe) if not pd.isna(reported_pe) else None
                )
                provider_reported_pb = (
                    float(reported_pb) if not pd.isna(reported_pb) else None
                )
                effective_date = pd.to_datetime(
                    latest_snapshot.get("effective_date"), errors="coerce"
                )
                provider_ratio_effective_date = (
                    effective_date.date().isoformat()
                    if not pd.isna(effective_date)
                    else None
                )
                period = latest_snapshot.get("period")
                provider_ratio_period = str(period) if not pd.isna(period) else None
    except FundamentalsNotFoundError:
        # Fundamentals are supplementary; price history remains usable for an
        # instrument which has no stored reports yet.
        fundamentals_history = None

    points = [
        SymbolPricePointResponse(
            date=timestamp.date().isoformat(),
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=(
                float(row["volume"])
                if "volume" in row and not pd.isna(row["volume"])
                else None
            ),
            eps_ttm=(
                float(eps_ttm.loc[timestamp])
                if timestamp in eps_ttm.index and not pd.isna(eps_ttm.loc[timestamp])
                else None
            ),
            shares_outstanding=(
                float(shares_outstanding.loc[timestamp])
                if timestamp in shares_outstanding.index
                and not pd.isna(shares_outstanding.loc[timestamp])
                else None
            ),
            trailing_pe=(
                float(trailing_pe.loc[timestamp])
                if timestamp in trailing_pe.index and not pd.isna(trailing_pe.loc[timestamp])
                else None
            ),
            trailing_pb=(
                float(trailing_pb.loc[timestamp])
                if timestamp in trailing_pb.index and not pd.isna(trailing_pb.loc[timestamp])
                else None
            ),
            relative_strength=(
                float(relative_strength.loc[timestamp])
                if timestamp in relative_strength.index
                and not pd.isna(relative_strength.loc[timestamp])
                else None
            ),
        )
        for timestamp, row in prices.data.iterrows()
    ]
    first_date = prices.data.index.min().date().isoformat()
    last_date = prices.data.index.max().date().isoformat()
    return SymbolPriceHistoryResponse(
        symbol=normalized,
        universe=normalized_universe,
        source=_metadata_source(stored.metadata.sources),
        price_basis=_display_price_basis(stored.metadata.price_basis),
        fetched_at=stored.metadata.fetched_at.isoformat(),
        first_date=first_date,
        last_date=last_date,
        row_count=len(prices.data),
        relative_strength_benchmark=relative_strength_benchmark,
        trailing_pe_source=(
            _metadata_source(fundamentals_history.metadata.sources)
            if fundamentals_history else None
        ),
        trailing_pe_method=(
            ", ".join(fundamentals_history.metadata.methodologies) or None
            if fundamentals_history
            else None
        ),
        trailing_pe_fetched_at=(
            fundamentals_history.metadata.fetched_at.isoformat()
            if fundamentals_history else None
        ),
        fundamentals_fields=(
            list(fundamentals_history.metadata.fields)
            if fundamentals_history else []
        ),
        provider_reported_pe=provider_reported_pe,
        provider_reported_pb=provider_reported_pb,
        provider_ratio_effective_date=provider_ratio_effective_date,
        provider_ratio_period=provider_ratio_period,
        shares_growth_pct=(
            float(shares_growth["total_growth_pct"]) if shares_growth else None
        ),
        shares_growth_cagr_pct=(
            float(shares_growth["cagr_pct"]) if shares_growth else None
        ),
        shares_growth_observed_years=(
            float(shares_growth["observed_years"]) if shares_growth else None
        ),
        shares_growth_start_date=(
            str(shares_growth["start_date"]) if shares_growth else None
        ),
        shares_growth_full_10y=(
            bool(shares_growth["full_period"]) if shares_growth else False
        ),
        shares_cagr_5y_pct=(
            float(shares_growth_5y["cagr_pct"]) if shares_growth_5y else None
        ),
        shares_cagr_5y_observed_years=(
            float(shares_growth_5y["observed_years"]) if shares_growth_5y else None
        ),
        shares_cagr_5y_start_date=(
            str(shares_growth_5y["start_date"]) if shares_growth_5y else None
        ),
        shares_cagr_full_5y=(
            bool(shares_growth_5y["full_period"]) if shares_growth_5y else False
        ),
        prices=points,
    )


def _metadata_source(sources: tuple[str, ...]) -> str:
    return sources[0] if len(sources) == 1 else ", ".join(sources)


def _display_price_basis(price_basis: str) -> str:
    return {
        "adjusted": "auto-adjusted OHLC",
        "provider_unspecified": "provider OHLC (adjustment unspecified)",
    }.get(price_basis, price_basis)


@router.post("/{market}/refresh", response_model=MarketDataJobResponse, status_code=202)
def refresh_market_data(
    market: str,
    mode: Literal["incremental", "full"] = Query(default="incremental"),
    dataset: Literal["prices", "fundamentals"] = Query(default="prices"),
) -> MarketDataJobResponse:
    normalized = _normalize_market(market)
    try:
        return MarketDataJobResponse(
            **start_refresh_job(normalized, mode, dataset).to_dict()
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/jobs/{job_id}", response_model=MarketDataJobResponse)
def market_data_job(job_id: str) -> MarketDataJobResponse:
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Refresh job not found")
    return MarketDataJobResponse(**job.to_dict())


@router.delete("/{market}", response_model=MarketDataClearResponse)
def clear_market_data(
    market: str,
    price_storage_service: Annotated[
        PriceStorageService, Depends(get_price_storage_service)
    ],
) -> MarketDataClearResponse:
    normalized = _normalize_market(market)
    market_code = "VN" if normalized.startswith("VN") else "US"
    affected_universes = _UNIVERSES_BY_MARKET[market_code]
    active = next(
        (universe for universe in affected_universes if get_active_job(universe)),
        None,
    )
    if active:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot clear {market_code} prices while {active} is refreshing",
        )
    result = price_storage_service.clear_market_for_universe(normalized)
    for universe in result.affected_universes:
        clear_job_history(universe)
    return MarketDataClearResponse(
        requested_universe=normalized,
        market=result.market,
        affected_universes=list(result.affected_universes),
        deleted_rows=result.deleted_rows,
        cleared=result.deleted_rows > 0,
    )
