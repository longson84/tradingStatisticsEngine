"""Factor analysis endpoints.

POST /factors/analyze   — time-series percentile breakdown for one symbol
POST /factors/universe  — cross-sectional breadth across N symbols
POST /factors/regime    — regime labels derived from cross-sectional breadth
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from trading_engine.types import FactorComputeError, InsufficientDataError

from trading_engine import analyze_factor, analyze_universe, detect_regime, zone_rarity_analysis
from trading_engine.factors.bollinger import BollingerBands
from trading_engine.factors.distance_from_peak import DistanceFromPeak
from trading_engine.factors.donchian import DonchianChannel
from trading_engine.factors.moving_average import MovingAverageRatio
from trading_engine.factors.ahr999 import AHR999
from trading_engine.types import Factor

from api.deps import fetch_prices
import numpy as np
import pandas as pd

from api.schemas.factor import (
    CrossSectionalRequest,
    CrossSectionalResponse,
    FactorRequest,
    FactorAnalysisResponse,
    RarityRequest,
    RarityAnalysisResponse,
    ZoneStatsSchema,
    ZoneEntrySchema,
    TimeSeriesPoint,
    EventStudyPath,
    EventStudyZone,
    RegimeRequest,
    RegimeResponse,
)
from api.utils import date_key

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
    if factor_type == "ahr999":
        return AHR999()
    raise HTTPException(status_code=400, detail=f"Unknown factor type: {factor_type!r}")


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

    try:
        factor = _build_factor(req.factor_type, req.period, req.ma_type, req.std_dev)
        factor_series = factor.compute(prices[req.symbol])
        result = analyze_factor(factor_series)
    except (FactorComputeError, InsufficientDataError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

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
    try:
        factor = _build_factor(req.factor_type, req.period, req.ma_type)
        result = analyze_universe(
            factor=factor,
            universe=req.symbols,
            prices=prices,
            threshold=req.threshold,
        )
    except (FactorComputeError, InsufficientDataError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return CrossSectionalResponse(
        factor_name=result.factor_name,
        universe=result.universe,
        breadth={date_key(ts): float(v) for ts, v in result.breadth.items()},
        pct_above={date_key(ts): float(v) for ts, v in result.pct_above.items()},
        universe_median={date_key(ts): float(v) for ts, v in result.universe_median.items()},
    )


@router.post("/regime", response_model=RegimeResponse)
def detect_regime_endpoint(req: RegimeRequest) -> RegimeResponse:
    prices = fetch_prices(
        req.symbols,
        req.date_range.start,
        req.date_range.end,
        req.data_source,
    )
    try:
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
    except (FactorComputeError, InsufficientDataError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return RegimeResponse(
        labels={date_key(ts): str(v) for ts, v in regime.labels.items()},
        breadth={date_key(ts): float(v) for ts, v in regime.breadth.items()},
    )


@router.post("/rarity", response_model=RarityAnalysisResponse)
def rarity_analysis_endpoint(req: RarityRequest) -> RarityAnalysisResponse:
    prices = fetch_prices(
        [req.symbol],
        req.date_range.start,
        req.date_range.end,
        req.data_source,
    )
    if req.symbol not in prices:
        raise HTTPException(status_code=422, detail=f"No data for symbol {req.symbol!r}")

    try:
        factor = _build_factor(req.factor_type, req.period, req.ma_type, req.std_dev)
        series = factor.compute(prices[req.symbol])
        result = zone_rarity_analysis(
            series=series,
            prices=prices[req.symbol],
            zones=req.zones,
            quick_recovery_days=req.quick_recovery_days,
        )
        # Attach factor-specific context (optional — not all factors implement context())
        factor_context = {}
        if hasattr(factor, "context"):
            factor_context = factor.context(prices[req.symbol])
        result.factor_context = factor_context

    except (FactorComputeError, InsufficientDataError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # ── Time series ───────────────────────────────────────────────────────────
    price_close = prices[req.symbol].data["close"]
    factor_vals = series.values.dropna()
    ts_points: list[TimeSeriesPoint] = []
    for ts, fv in factor_vals.items():
        if ts in price_close.index:
            ts_points.append(TimeSeriesPoint(
                date=ts.strftime("%Y-%m-%d"),
                price=float(price_close[ts]),
                factor=float(fv),
            ))

    # ── Forward returns & Event study ─────────────────────────────────────────
    price_arr = price_close.values.astype(float)
    dates_idx = price_close.index
    date_to_pos = {ts: i for i, ts in enumerate(dates_idx)}

    _FWD_BARS = [20, 50, 100, 150, 200]
    _n = len(price_arr)

    def _forward_returns(start_date, entry_price: float) -> dict[str, float | None]:
        pos = date_to_pos.get(pd.Timestamp(start_date))
        if pos is None or entry_price <= 0:
            return {str(b): None for b in _FWD_BARS}
        return {
            str(b): float((price_arr[pos + b] - entry_price) / entry_price * 100)
                    if pos + b < _n else None
            for b in _FWD_BARS
        }

    day_offsets = np.arange(-10, 91)           # 101 sessions

    study_zones = [z for z in req.zones if z <= 25]
    event_study_data: list[EventStudyZone] = []

    for zone_pct in study_zones:
        zone_entries = [e for e in result.entries if e.zone_pct == zone_pct]
        valid = [(e, date_to_pos.get(pd.Timestamp(e.start_date))) for e in zone_entries]
        valid = [(e, idx) for e, idx in valid if idx is not None]
        if len(valid) < 3:
            continue

        # returns matrix: shape (n_entries, 101)
        ret_matrix = np.full((len(valid), len(day_offsets)), np.nan)
        for i, (_, entry_idx) in enumerate(valid):
            ep = price_arr[entry_idx]
            if ep <= 0:
                continue
            target = entry_idx + day_offsets
            mask = (target >= 0) & (target < len(price_arr))
            ret_matrix[i, mask] = (price_arr[target[mask]] - ep) / ep * 100

        paths: list[EventStudyPath] = []
        for j, day in enumerate(day_offsets):
            col = ret_matrix[:, j]
            vals = col[~np.isnan(col)]
            if len(vals) >= 3:
                paths.append(EventStudyPath(
                    day=int(day),
                    mean=float(np.mean(vals)),
                    p25=float(np.percentile(vals, 25)),
                    p75=float(np.percentile(vals, 75)),
                ))

        if paths:
            event_study_data.append(EventStudyZone(
                zone_pct=zone_pct,
                count=len(valid),
                paths=paths,
            ))

    return RarityAnalysisResponse(
        factor_name=result.factor_name,
        symbol=result.symbol,
        stats_date=result.stats_date,
        first_date=result.first_date,
        last_date=result.last_date,
        total_bars=result.total_bars,
        current_price=result.current_price,
        current_value=result.current_value,
        current_percentile=result.current_percentile,
        current_zone=result.current_zone,
        zone_entry_date=result.zone_entry_date,
        zone_entry_price=result.zone_entry_price,
        sessions_in_zone=result.sessions_in_zone,
        max_potential_drop_pct=result.max_potential_drop_pct,
        factor_context=result.factor_context,
        zone_stats=[
            ZoneStatsSchema(
                zone_pct=s.zone_pct,
                threshold_value=s.threshold_value,
                count=s.count,
                qr_count=s.qr_count,
                qr_pct=s.qr_pct,
                count_5y=s.count_5y,
                qr_5y=s.qr_5y,
                count_10y=s.count_10y,
                qr_10y=s.qr_10y,
                avg_days=s.avg_days,
                mmae_pct=s.mmae_pct,
                mae_by_percentile={str(k): v for k, v in s.mae_by_percentile.items()},
                is_current_zone=s.is_current_zone,
            )
            for s in result.zone_stats
        ],
        entries=[
            ZoneEntrySchema(
                zone_pct=e.zone_pct,
                start_date=e.start_date,
                entry_price=e.entry_price,
                entry_factor=e.entry_factor,
                low_price=e.low_price,
                low_date=e.low_date,
                low_factor=e.low_factor,
                mae_pct=e.mae_pct,
                days_to_low=e.days_to_low,
                recovery_date=e.recovery_date,
                days_to_recovery=e.days_to_recovery,
                bars_elapsed=e.bars_elapsed,
                forward_returns=_forward_returns(e.start_date, e.entry_price),
                is_active=e.is_active,
                is_quick_recovery=e.is_quick_recovery,
                level=e.level,
                children_count=e.children_count,
                parent_zone_pct=e.parent_zone_pct,
                parent_start_date=e.parent_start_date,
            )
            for e in result.entries
        ],
        time_series=ts_points,
        event_study=event_study_data,
    )
