"""Factor analysis endpoints.

POST /factors/analyze   — time-series percentile breakdown for one symbol
POST /factors/universe  — cross-sectional breadth across N symbols
POST /factors/regime    — regime labels derived from cross-sectional breadth
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from trading_engine.types import FactorComputeError, InsufficientDataError, PriceFrame

from trading_engine import analyze_factor, analyze_universe, detect_regime, zone_rarity_analysis
from trading_engine.factors.bollinger import BollingerBands
from trading_engine.factors.distance_from_peak import DistanceFromPeak
from trading_engine.factors.donchian import DonchianChannel
from trading_engine.factors.moving_average import DistanceFromMovingAverage, MovingAverageRatio
from trading_engine.factors.ahr999 import AHR999
from trading_engine.types import Factor

from api.deps import (
    fetch_prices,
    get_instrument_analysis_service,
    get_watchlist_service,
)
from api.services.instrument_analysis_service import (
    InstrumentAnalysisService,
    InstrumentPriceUnavailableError,
    UnknownInstrumentError,
)
from api.services.watchlist_service import UnknownWatchlistError, WatchlistService
import pandas as pd

from api.schemas.factor import (
    CrossSectionalRequest,
    CrossSectionalResponse,
    FactorRequest,
    FactorAnalysisResponse,
    RarityRequest,
    RarityAnalysisResponse,
    PredefinedRarityRequest,
    PredefinedRarityResponse,
    PredefinedRarityInstrumentStatus,
    PredefinedRarityRow,
    PredefinedRarityTable,
    ZoneStatsSchema,
    ZoneEntrySchema,
    TimeSeriesPoint,
    RegimeRequest,
    RegimeResponse,
)
from api.utils import date_key

router = APIRouter(prefix="/factors", tags=["factors"])

_PREDEFINED_PERCENTILES = [5, 10, 15, 20, 25, 50, 75, 80, 90, 95]
_PREDEFINED_FACTORS: tuple[tuple[str, str, Factor], ...] = (
    (
        "distance_ma50",
        "Distance from MA50",
        DistanceFromMovingAverage(ma_type="SMA", length=50),
    ),
    (
        "distance_ma100",
        "Distance from MA100",
        DistanceFromMovingAverage(ma_type="SMA", length=100),
    ),
    (
        "distance_ma150",
        "Distance from MA150",
        DistanceFromMovingAverage(ma_type="SMA", length=150),
    ),
    (
        "distance_ma200",
        "Distance from MA200",
        DistanceFromMovingAverage(ma_type="SMA", length=200),
    ),
    ("distance_high_100", "Distance from Highest 100 Days", DistanceFromPeak(window=100)),
    ("distance_high_150", "Distance from Highest 150 Days", DistanceFromPeak(window=150)),
    ("distance_high_200", "Distance from Highest 200 Days", DistanceFromPeak(window=200)),
)


def _build_factor(factor_type: str, period: int, ma_type: str, std_dev: float = 2.0) -> Factor:
    if factor_type == "moving_average":
        return MovingAverageRatio(ma_type=ma_type.upper(), length=period)
    if factor_type == "distance_from_ma":
        return DistanceFromMovingAverage(ma_type=ma_type.upper(), length=period)
    if factor_type == "bollinger":
        return BollingerBands(period=period, num_std=std_dev)
    if factor_type == "donchian":
        return DonchianChannel(entry_length=period, exit_length=max(1, period // 2))
    if factor_type == "distance_from_peak":
        return DistanceFromPeak(window=period)
    if factor_type == "ahr999":
        return AHR999()
    raise HTTPException(status_code=400, detail=f"Unknown factor type: {factor_type!r}")


def _predefined_row(
    instrument_id: int, symbol: str, factor: Factor, prices: PriceFrame
) -> PredefinedRarityRow:
    series = factor.compute(prices)
    values = series.values.dropna()
    if values.empty:
        raise InsufficientDataError(f"No factor values for {symbol}")

    current = float(values.iloc[-1])
    percentile_values = values.quantile([p / 100 for p in _PREDEFINED_PERCENTILES])
    factor_context = factor.context(prices) if hasattr(factor, "context") else {}
    reference_price = factor_context.get("ma_value", factor_context.get("peak_price"))
    if reference_price is None:
        raise InsufficientDataError(f"No reference price for {symbol}")
    p50 = float(percentile_values.loc[0.5])

    return PredefinedRarityRow(
        instrument_id=instrument_id,
        symbol=symbol,
        first_date=values.index[0].date(),
        last_date=values.index[-1].date(),
        observations=len(values),
        reference_price=float(reference_price),
        p50_price=float(reference_price) * (1 + p50),
        current_price=float(reference_price) * (1 + current),
        current_value_pct=current * 100,
        current_percentile=float((values <= current).mean() * 100),
        percentiles={
            f"p{p}": float(percentile_values.loc[p / 100] * 100)
            for p in _PREDEFINED_PERCENTILES
        },
    )


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


@router.post("/predefined-rarity", response_model=PredefinedRarityResponse)
def predefined_rarity_endpoint(
    req: PredefinedRarityRequest,
    watchlist_service: Annotated[
        WatchlistService, Depends(get_watchlist_service)
    ],
    instrument_service: Annotated[
        InstrumentAnalysisService, Depends(get_instrument_analysis_service)
    ],
) -> PredefinedRarityResponse:
    try:
        watchlist = watchlist_service.get_watchlist(req.watchlist_id)
    except UnknownWatchlistError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    instrument_ids = [member.instrument_id for member in watchlist.members]
    if not instrument_ids:
        raise HTTPException(status_code=422, detail="Watchlist has no instruments")

    stored = instrument_service.get_stored_histories(instrument_ids)
    prices = stored.prices
    if not prices:
        raise HTTPException(
            status_code=422,
            detail="No watchlist instruments have stored PostgreSQL price history",
        )

    errors = [
        f"{member.symbol} (instrument {member.instrument_id}): "
        "no stored PostgreSQL price history"
        for member in watchlist.members
        if member.instrument_id in stored.missing_instrument_ids
    ]
    if stored.stale_instrument_ids:
        stale_labels = [
            f"{member.symbol} ({member.instrument_id})"
            for member in watchlist.members
            if member.instrument_id in stored.stale_instrument_ids
        ]
        errors.append(
            "Stale through each instrument's expected session: "
            + ", ".join(stale_labels)
        )
    tables: list[PredefinedRarityTable] = []

    for factor_key, factor_name, factor in _PREDEFINED_FACTORS:
        rows: list[PredefinedRarityRow] = []
        for member in watchlist.members:
            if member.instrument_id not in prices:
                continue
            try:
                rows.append(_predefined_row(
                    member.instrument_id,
                    member.symbol,
                    factor,
                    prices[member.instrument_id],
                ))
            except (FactorComputeError, InsufficientDataError, ValueError) as exc:
                errors.append(f"{member.symbol} / {factor_name}: {exc}")

        tables.append(
            PredefinedRarityTable(
                factor_key=factor_key,
                factor_name=factor_name,
                rows=rows,
            )
        )

    statuses = []
    for member in watchlist.members:
        instrument = stored.instruments.get(member.instrument_id)
        available = member.instrument_id in prices
        statuses.append(PredefinedRarityInstrumentStatus(
            instrument_id=member.instrument_id,
            symbol=member.symbol,
            instrument_type=member.instrument_type,
            company_name=member.company_name,
            venue_code=member.venue_code,
            venue_name=member.venue_name,
            base_asset=member.base_asset,
            quote_asset=member.quote_asset,
            currency=member.currency,
            price_basis=instrument.price_basis if instrument is not None else None,
            price_source=stored.price_sources.get(member.instrument_id),
            expected_last_session=stored.expected_last_sessions.get(member.instrument_id),
            data_last_session=stored.data_last_sessions.get(member.instrument_id),
            available=available,
            is_stale=member.instrument_id in stored.stale_instrument_ids,
        ))

    return PredefinedRarityResponse(
        watchlist_id=watchlist.id,
        watchlist_name=watchlist.name,
        requested_instruments=len(instrument_ids),
        available_instruments=len(prices),
        stale_instrument_ids=list(stored.stale_instrument_ids),
        missing_instrument_ids=list(stored.missing_instrument_ids),
        instruments=statuses,
        percentile_columns=[f"p{p}" for p in _PREDEFINED_PERCENTILES],
        tables=tables,
        errors=errors,
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
def rarity_analysis_endpoint(
    req: RarityRequest,
    price_service: Annotated[
        InstrumentAnalysisService, Depends(get_instrument_analysis_service)
    ],
) -> RarityAnalysisResponse:
    try:
        stored = price_service.get_current_history(req.instrument_id)
    except UnknownInstrumentError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InstrumentPriceUnavailableError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    prices = stored.prices

    try:
        factor = _build_factor(req.factor_type, req.period, req.ma_type, req.std_dev)
        series = factor.compute(prices)
        result = zone_rarity_analysis(
            series=series,
            prices=prices,
            zones=req.zones,
            quick_recovery_days=req.quick_recovery_days,
            recovery_mode=req.recovery_mode,
        )
        # Attach factor-specific context (optional — not all factors implement context())
        factor_context = {}
        if hasattr(factor, "context"):
            factor_context = factor.context(prices)
        result.factor_context = factor_context

    except (FactorComputeError, InsufficientDataError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # ── Time series ───────────────────────────────────────────────────────────
    price_close = prices.data["close"]
    factor_vals = series.values.dropna()
    ts_points: list[TimeSeriesPoint] = []
    for ts, fv in factor_vals.items():
        if ts in price_close.index:
            ts_points.append(TimeSeriesPoint(
                date=ts.strftime("%Y-%m-%d"),
                price=float(price_close[ts]),
                factor=float(fv),
            ))

    # ── Forward returns ───────────────────────────────────────────────────────
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

    return RarityAnalysisResponse(
        instrument_id=stored.instrument.id,
        factor_name=result.factor_name,
        symbol=result.symbol,
        instrument_type=stored.instrument.instrument_type,
        company_name=stored.instrument.company_name,
        venue_code=stored.instrument.venue_code,
        venue_name=stored.instrument.venue_name,
        base_asset=stored.instrument.base_asset,
        quote_asset=stored.instrument.quote_asset,
        currency=stored.instrument.currency,
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
        expected_last_session=stored.expected_last_session,
        data_last_session=stored.data_last_session,
        refreshed=stored.refreshed,
        is_stale=stored.is_stale,
        refresh_warning=stored.refresh_warning,
        price_source=stored.price_source,
        price_basis=stored.price_basis,
    )
