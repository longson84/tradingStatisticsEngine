"""Market-health endpoint computed from canonical PostgreSQL price history."""
from __future__ import annotations

import math

from datetime import date, timedelta
from typing import Annotated

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import get_price_history_service
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
    InsufficientDataError,
    MarketHealthWeights,
)
from api.services.price_history_service import (
    PriceHistoryNotFoundError,
    PriceHistoryService,
    UnknownPriceUniverseError,
)


router = APIRouter(prefix="/market-health", tags=["market-health"])
_UNIVERSES = ("US500", "US2000", "US100", "VN100", "VN30")
_DISPLAY_YEARS = 5


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
    price_history_service: Annotated[
        PriceHistoryService, Depends(get_price_history_service)
    ],
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
        stored = price_history_service.get_universe_history(
            normalized,
            start=date_value - timedelta(days=window * 2),
            end=date_value,
        )
        stocks = compute_market_distance_snapshot(
            stored.prices,
            as_of=date_value,
            window=window,
            min_distance=min_distance,
            max_distance=max_distance,
        )
    except (
        PriceHistoryNotFoundError,
        UnknownPriceUniverseError,
        InsufficientDataError,
        ValueError,
    ) as exc:
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
def run_market_health(
    req: MarketHealthRunRequest,
    price_history_service: Annotated[
        PriceHistoryService, Depends(get_price_history_service)
    ],
) -> MarketHealthRunResponse:
    weights = MarketHealthWeights(**req.weights.model_dump())
    markets: list[MarketHealthUniverseResponse] = []

    for universe in _UNIVERSES:
        try:
            latest_date = price_history_service.get_latest_date(universe)
            display_start = _subtract_years(latest_date, _DISPLAY_YEARS)
            load_start = display_start - timedelta(days=req.window * 2)
            stored = price_history_service.get_universe_history(
                universe, start=load_start, end=latest_date
            )
            result = compute_market_health(
                stored.prices,
                universe=universe,
                weights=weights,
                window=req.window,
                minimum_coverage=req.minimum_coverage,
            )
            displayed_series = result.series.loc[pd.Timestamp(display_start):]
            if displayed_series.empty:
                raise InsufficientDataError(
                    f"No market-health observations on or after {display_start}"
                )
        except (
            PriceHistoryNotFoundError,
            UnknownPriceUniverseError,
            InsufficientDataError,
            ValueError,
        ) as exc:
            raise HTTPException(status_code=422, detail=f"{universe}: {exc}") from exc

        points = [_point(timestamp, row) for timestamp, row in displayed_series.iterrows()]
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
                    fetched_at=stored.metadata.fetched_at.isoformat(),
                    first_date=stored.metadata.first_date,
                    last_date=stored.metadata.last_date,
                    symbol_count=stored.metadata.symbol_count,
                    source=_metadata_source(stored.metadata.sources),
                    price_basis=_display_price_basis(stored.metadata.price_basis),
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


def _subtract_years(value: date, years: int) -> date:
    try:
        return value.replace(year=value.year - years)
    except ValueError:
        return value.replace(month=2, day=28, year=value.year - years)


def _metadata_source(sources: tuple[str, ...]) -> str:
    return sources[0] if len(sources) == 1 else ", ".join(sources)


def _display_price_basis(price_basis: str) -> str:
    return {
        "adjusted": "auto-adjusted OHLC",
        "provider_unspecified": "provider OHLC (adjustment unspecified)",
    }.get(price_basis, price_basis)
