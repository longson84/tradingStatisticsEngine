"""Market-health endpoint computed entirely from persistent local history caches."""
from __future__ import annotations

import math

from datetime import date

from fastapi import APIRouter, HTTPException, Query

from api.market_history import load_cached_market_history
from api.schemas.market_health import (
    MarketHealthPointResponse,
    MarketHealthDistributionBucketResponse,
    MarketHealthDistributionResponse,
    MarketHealthRunRequest,
    MarketHealthRunResponse,
    MarketHealthUniverseResponse,
    MarketHealthStockDistanceResponse,
    MarketHistoryCacheResponse,
)
from trading_engine.factor_analysis.market_health import (
    classify_market_health,
    compute_market_distance_snapshot,
    compute_market_health,
)
from trading_engine.types import (
    DataLoadError,
    InsufficientDataError,
    MarketHealthWeights,
)


router = APIRouter(prefix="/market-health", tags=["market-health"])
_UNIVERSES = ("US500", "US2000", "US100", "VN100", "VN30")


def _optional_number(value: float) -> float | None:
    return None if math.isnan(value) else float(value)


def _point(timestamp, row) -> MarketHealthPointResponse:
    return MarketHealthPointResponse(
        date=timestamp.date(),
        health_score=float(row["health_score"]),
        median_distance=float(row["median_distance"]),
        p10_distance=float(row["p10_distance"]),
        p20_distance=float(row["p20_distance"]),
        p80_distance=float(row["p80_distance"]),
        p90_distance=float(row["p90_distance"]),
        within_10=float(row["within_10"]),
        within_20=float(row["within_20"]),
        within_30=float(row["within_30"]),
        stress_40=float(row["stress_40"]),
        coverage_pct=float(row["coverage_pct"]),
        eligible_count=int(row["eligible_count"]),
        change_5=_optional_number(float(row["change_5"])),
        change_20=_optional_number(float(row["change_20"])),
        ema_gap=float(row["ema_gap"]),
    )


@router.get("/{universe}/distribution", response_model=MarketHealthDistributionResponse)
def market_health_distribution(
    universe: str,
    date_value: date = Query(alias="date"),
    window: int = Query(default=200, ge=20, le=500),
    min_distance: float | None = Query(default=None),
    max_distance: float | None = Query(default=None),
) -> MarketHealthDistributionResponse:
    normalized = universe.upper()
    if normalized not in _UNIVERSES:
        raise HTTPException(status_code=404, detail=f"Unsupported market: {universe}")
    if (
        min_distance is not None
        and max_distance is not None
        and min_distance >= max_distance
    ):
        raise HTTPException(
            status_code=422,
            detail="min_distance must be lower than max_distance",
        )
    try:
        prices, _ = load_cached_market_history(normalized)
        stocks = compute_market_distance_snapshot(
            prices,
            as_of=date_value,
            window=window,
            min_distance=min_distance,
            max_distance=max_distance,
        )
    except (DataLoadError, InsufficientDataError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"{normalized}: {exc}") from exc
    return MarketHealthDistributionResponse(
        universe=normalized,
        date=date_value,
        window=window,
        min_distance=min_distance,
        max_distance=max_distance,
        stocks=[MarketHealthStockDistanceResponse(**stock.__dict__) for stock in stocks],
    )


@router.post("/run", response_model=MarketHealthRunResponse)
def run_market_health(req: MarketHealthRunRequest) -> MarketHealthRunResponse:
    weights = MarketHealthWeights(**req.weights.model_dump())
    markets: list[MarketHealthUniverseResponse] = []

    for universe in _UNIVERSES:
        try:
            prices, manifest = load_cached_market_history(universe)
            result = compute_market_health(
                prices,
                universe=universe,
                weights=weights,
                window=req.window,
                minimum_coverage=req.minimum_coverage,
            )
        except (DataLoadError, InsufficientDataError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=f"{universe}: {exc}") from exc

        points = [_point(timestamp, row) for timestamp, row in result.series.iterrows()]
        current = points[-1]
        markets.append(
            MarketHealthUniverseResponse(
                universe=universe,
                universe_size=result.universe_size,
                regime=classify_market_health(
                    current.health_score,
                    current.change_20,
                ),
                cache=MarketHistoryCacheResponse(
                    fetched_at=str(manifest["fetched_at"]),
                    first_date=manifest["first_date"],
                    last_date=manifest["last_date"],
                    symbol_count=int(manifest["symbol_count"]),
                    source=str(manifest["source"]),
                    price_basis=str(manifest["price_basis"]),
                ),
                current=current,
                series=points,
                distribution=[
                    MarketHealthDistributionBucketResponse(
                        label=bucket.label,
                        min_distance=bucket.min_distance,
                        max_distance=bucket.max_distance,
                        count=bucket.count,
                        percentage=bucket.percentage,
                        cumulative_percentage=bucket.cumulative_percentage,
                    )
                    for bucket in result.distribution
                ],
            )
        )

    return MarketHealthRunResponse(
        window=req.window,
        minimum_coverage=req.minimum_coverage,
        weights=req.weights,
        markets=markets,
    )
