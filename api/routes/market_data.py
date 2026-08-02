"""Endpoints for inspecting and maintaining local market-history caches."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from api.market_data_jobs import (
    clear_job_history,
    get_active_job,
    get_job,
    get_latest_job,
    start_refresh_job,
)
from api.fundamentals_cache import (
    DEFAULT_FUNDAMENTALS_DIR,
    fundamentals_cache_status,
    load_cached_fundamentals,
    universe_symbols,
)
from api.market_history import (
    DEFAULT_CACHE_DIR,
    SUPPORTED_UNIVERSES,
    load_cached_market_symbol,
)
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


router = APIRouter(prefix="/market-data", tags=["market-data"])


def _normalize_market(market: str) -> str:
    normalized = market.upper()
    if normalized not in SUPPORTED_UNIVERSES:
        raise HTTPException(status_code=404, detail=f"Unsupported market: {market}")
    return normalized


def _cache_status(
    universe: str,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    fundamentals_dir: Path = DEFAULT_FUNDAMENTALS_DIR,
) -> MarketDataCacheStatus:
    csv_path = cache_dir / f"{universe.lower()}.csv"
    manifest_path = cache_dir / f"{universe.lower()}.json"
    latest_job = get_latest_job(universe)
    fundamentals_job = get_latest_job(universe, "fundamentals")
    market = "VN" if universe.startswith("VN") else "US"
    fundamental_status = fundamentals_cache_status(
        universe_symbols(universe), market, cache_dir=fundamentals_dir
    )
    base = {
        "universe": universe,
        "exists": csv_path.exists() and manifest_path.exists(),
        "size_bytes": csv_path.stat().st_size if csv_path.exists() else 0,
        "latest_job": latest_job.to_dict() if latest_job else None,
        "latest_fundamentals_job": (
            fundamentals_job.to_dict() if fundamentals_job else None
        ),
        "fundamentals_exists": fundamental_status["exists"],
        "fundamentals_fetched_at": fundamental_status["fetched_at"],
        "fundamentals_symbol_count": fundamental_status["symbol_count"],
        "fundamentals_snapshot_count": fundamental_status["snapshot_count"],
        "fundamentals_size_bytes": fundamental_status["size_bytes"],
    }
    if not base["exists"]:
        return MarketDataCacheStatus(**base)
    try:
        manifest = json.loads(manifest_path.read_text())
    except (json.JSONDecodeError, OSError):
        return MarketDataCacheStatus(**base, errors=[{"cache": "Invalid manifest"}])
    return MarketDataCacheStatus(
        **base,
        fetched_at=manifest.get("fetched_at"),
        first_date=manifest.get("first_date"),
        last_date=manifest.get("last_date"),
        symbol_count=manifest.get("symbol_count"),
        row_count=manifest.get("row_count"),
        source=manifest.get("source"),
        price_basis=manifest.get("price_basis"),
        errors=manifest.get("errors", []),
    )


@router.get("/status", response_model=MarketDataStatusResponse)
def market_data_status() -> MarketDataStatusResponse:
    return MarketDataStatusResponse(
        cache_directory=str(DEFAULT_CACHE_DIR),
        fundamentals_cache_directory=str(DEFAULT_FUNDAMENTALS_DIR),
        markets=[
            _cache_status(universe)
            for universe in ("US500", "US2000", "US100", "VN100", "VN30")
        ],
    )


@router.get("/symbols/{symbol}/history", response_model=SymbolPriceHistoryResponse)
def symbol_price_history(
    symbol: str,
    universe: str = Query(...),
) -> SymbolPriceHistoryResponse:
    normalized = symbol.upper().strip()
    normalized_universe = _normalize_market(universe)
    try:
        prices, manifest = load_cached_market_symbol(normalized_universe, normalized)
    except DataLoadError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    fundamentals_manifest = None
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
        snapshots, fundamentals_manifest = load_cached_fundamentals(normalized, market)
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
    except Exception:
        # Fundamentals are supplementary; cached price history remains usable if
        # a provider temporarily fails or a company has no reported EPS history.
        fundamentals_manifest = None

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
        source=str(manifest["source"]),
        price_basis=str(manifest["price_basis"]),
        fetched_at=str(manifest["fetched_at"]),
        first_date=first_date,
        last_date=last_date,
        row_count=len(prices.data),
        relative_strength_benchmark=relative_strength_benchmark,
        trailing_pe_source=(
            str(fundamentals_manifest["source"]) if fundamentals_manifest else None
        ),
        trailing_pe_method=(
            str(fundamentals_manifest["method"]) if fundamentals_manifest else None
        ),
        trailing_pe_fetched_at=(
            str(fundamentals_manifest["fetched_at"]) if fundamentals_manifest else None
        ),
        fundamentals_fields=(
            list(fundamentals_manifest.get("fields", []))
            if fundamentals_manifest else []
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
def clear_market_data(market: str) -> MarketDataClearResponse:
    normalized = _normalize_market(market)
    if get_active_job(normalized):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot clear {normalized} while its refresh is running",
        )
    cleared = False
    stem = normalized.lower()
    for suffix in (".csv", ".json", ".refresh.csv", ".refresh.json"):
        path = DEFAULT_CACHE_DIR / f"{stem}{suffix}"
        if path.exists():
            path.unlink()
            cleared = True
    clear_job_history(normalized)
    return MarketDataClearResponse(universe=normalized, cleared=cleared)
