"""Factor analysis endpoints.

POST /factors/analyze   — time-series percentile breakdown for one symbol
POST /factors/universe  — cross-sectional breadth across N symbols
POST /factors/regime    — regime labels derived from cross-sectional breadth
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from trading_engine import analyze_factor, analyze_universe, detect_regime
from trading_engine.factors.bollinger import BollingerBands
from trading_engine.factors.distance_from_peak import DistanceFromPeak
from trading_engine.factors.donchian import DonchianChannel
from trading_engine.factors.moving_average import MovingAverageRatio
from trading_engine.types import Factor

from api.deps import fetch_prices
from api.schemas.factor import (
    CrossSectionalRequest,
    CrossSectionalResponse,
    FactorRequest,
    FactorAnalysisResponse,
    RegimeRequest,
    RegimeResponse,
)

router = APIRouter(prefix="/factors", tags=["factors"])


def _build_factor(factor_type: str, period: int, ma_type: str, std_dev: float = 2.0) -> Factor:
    if factor_type == "moving_average":
        return MovingAverageRatio(ma_type=ma_type.upper(), length=period)
    if factor_type == "bollinger":
        return BollingerBands(period=period, num_std=std_dev)
    if factor_type == "donchian":
        return DonchianChannel(entry_length=period, exit_length=max(1, period // 2))
    if factor_type == "distance_from_peak":
        return DistanceFromPeak(window=period)
    raise HTTPException(status_code=400, detail=f"Unknown factor type: {factor_type!r}")


def _date_key(ts) -> str:
    return str(ts.date()) if hasattr(ts, "date") and callable(ts.date) else str(ts)


@router.post("/analyze", response_model=FactorAnalysisResponse)
def analyze_factor_endpoint(req: FactorRequest) -> FactorAnalysisResponse:
    prices = fetch_prices(
        [req.symbol],
        req.date_range.start,
        req.date_range.end,
        req.data_source,
    )
    if req.symbol not in prices:
        raise HTTPException(status_code=422, detail=f"No data for symbol {req.symbol!r}")

    factor = _build_factor(req.factor_type, req.period, req.ma_type, req.std_dev)
    factor_series = factor.compute(prices[req.symbol])
    result = analyze_factor(factor_series)

    return FactorAnalysisResponse(
        factor_name=result.factor_name,
        current_value=result.current_value,
        current_percentile=result.current_percentile,
        history_length_days=result.history_length_days,
        percentiles={f"p{k}": v for k, v in result.percentiles.items()},
    )


@router.post("/universe", response_model=CrossSectionalResponse)
def analyze_universe_endpoint(req: CrossSectionalRequest) -> CrossSectionalResponse:
    prices = fetch_prices(
        req.symbols,
        req.date_range.start,
        req.date_range.end,
        req.data_source,
    )
    factor = _build_factor(req.factor_type, req.period, req.ma_type)
    result = analyze_universe(
        factor=factor,
        universe=req.symbols,
        prices=prices,
        threshold=req.threshold,
    )

    return CrossSectionalResponse(
        factor_name=result.factor_name,
        universe=result.universe,
        breadth={_date_key(ts): float(v) for ts, v in result.breadth.items()},
        pct_above={_date_key(ts): float(v) for ts, v in result.pct_above.items()},
        universe_median={_date_key(ts): float(v) for ts, v in result.universe_median.items()},
    )


@router.post("/regime", response_model=RegimeResponse)
def detect_regime_endpoint(req: RegimeRequest) -> RegimeResponse:
    prices = fetch_prices(
        req.symbols,
        req.date_range.start,
        req.date_range.end,
        req.data_source,
    )
    factor = _build_factor(req.factor_type, req.period, req.ma_type)
    cross = analyze_universe(
        factor=factor,
        universe=req.symbols,
        prices=prices,
        threshold=req.threshold,
    )
    regime = detect_regime(
        breadth=cross.breadth,
        thresholds=(req.lower_threshold, req.upper_threshold),
    )

    return RegimeResponse(
        labels={_date_key(ts): str(v) for ts, v in regime.labels.items()},
        breadth={_date_key(ts): float(v) for ts, v in regime.breadth.items()},
    )
