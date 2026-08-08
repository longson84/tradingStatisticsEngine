"""Market-health endpoint computed from canonical PostgreSQL price history."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import get_market_health_data_service, get_price_history_service
from api.schemas.market_health import (
    MarketHealthPointResponse,
    MarketHealthDistributionBucketResponse,
    MarketHealthDistributionResponse,
    MarketHealthHistoricalContextResponse,
    MarketHealthRunRequest,
    MarketHealthRunResponse,
    MarketHealthSeriesPointResponse,
    MarketHealthUniverseResponse,
    MarketHealthStockDistanceResponse,
    MarketHistoryCacheResponse,
)
from trading_engine.factor_analysis.market_health import (
    compute_market_distance_snapshot,
    compute_market_health_from_closes,
    compute_market_health_running_medians,
    summarize_market_health_history,
)
from trading_engine.types import InsufficientDataError
from api.services.price_history_service import (
    PriceHistoryNotFoundError,
    PriceHistoryService,
    UnknownPriceUniverseError,
)
from api.services.market_health_data_service import MarketHealthDataService


router = APIRouter(prefix="/market-health", tags=["market-health"])
_UNIVERSES = (
    "US500", "US2000", "US100",
    "VNALL", "VN100", "VN30", "VNMID", "VNSML",
)
_DISPLAY_YEARS = 10
_MAX_RUNNING_MEDIAN_YEARS = 10


def _point(timestamp, row) -> MarketHealthPointResponse:
    return MarketHealthPointResponse(
        date=timestamp.date(),
        median_distance=float(row["median_distance"]),
        coverage_pct=float(row["coverage_pct"]),
        eligible_count=int(row["eligible_count"]),
    )


def _series_point(timestamp, row) -> MarketHealthSeriesPointResponse:
    return MarketHealthSeriesPointResponse(
        date=timestamp.date(),
        median_distance=float(row["median_distance"]),
        running_median_10y=float(row["running_median_10y"]),
        running_median_5y=float(row["running_median_5y"]),
        running_median_1y=float(row["running_median_1y"]),
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
    market_health_data_service: Annotated[
        MarketHealthDataService, Depends(get_market_health_data_service)
    ],
) -> MarketHealthRunResponse:
    markets: list[MarketHealthUniverseResponse] = []

    for universe in tuple(dict.fromkeys(req.universes)):
        try:
            latest_date = market_health_data_service.get_latest_date(universe)
            display_start = _subtract_years(latest_date, _DISPLAY_YEARS)
            running_start = _subtract_years(
                display_start, _MAX_RUNNING_MEDIAN_YEARS
            )
            load_start = running_start - timedelta(days=req.window * 2)
            stored = market_health_data_service.get_close_history(
                universe, start=load_start, end=latest_date
            )
            result = compute_market_health_from_closes(
                stored.closes,
                universe=universe,
                window=req.window,
                minimum_coverage=req.minimum_coverage,
            )
            series_with_medians = result.series.join(
                compute_market_health_running_medians(
                    result.series["median_distance"]
                )
            )
            displayed_series = series_with_medians.loc[pd.Timestamp(display_start):]
            if displayed_series.empty:
                raise InsufficientDataError(
                    f"No market-health observations on or after {display_start}"
                )
            historical_context = summarize_market_health_history(
                displayed_series["median_distance"]
            )
        except (
            PriceHistoryNotFoundError,
            UnknownPriceUniverseError,
            InsufficientDataError,
            ValueError,
        ) as exc:
            raise HTTPException(status_code=422, detail=f"{universe}: {exc}") from exc

        points = [
            _series_point(timestamp, row)
            for timestamp, row in displayed_series.iterrows()
        ]
        current = _point(displayed_series.index[-1], displayed_series.iloc[-1])
        markets.append(
            MarketHealthUniverseResponse(
                universe=universe,
                universe_size=result.universe_size,
                cache=MarketHistoryCacheResponse(
                    fetched_at=stored.metadata.fetched_at.isoformat(),
                    first_date=stored.metadata.first_date,
                    last_date=stored.metadata.last_date,
                    symbol_count=stored.metadata.symbol_count,
                    source=_metadata_source(stored.metadata.sources),
                    price_basis=_display_price_basis(stored.metadata.price_basis),
                ),
                current=current,
                historical_context=MarketHealthHistoricalContextResponse(
                    **historical_context.__dict__
                ),
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
