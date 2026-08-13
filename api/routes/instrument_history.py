"""Stored price and point-in-time fundamental history by exact instrument."""
from __future__ import annotations

from typing import Annotated

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_fundamental_service, get_instrument_analysis_service
from api.schemas.instrument import (
    InstrumentPriceHistoryResponse,
    InstrumentPricePointResponse,
)
from api.services.fundamental_service import FundamentalService, FundamentalsNotFoundError
from api.services.instrument_analysis_service import (
    InstrumentAnalysisService,
    InstrumentPriceUnavailableError,
    UnknownInstrumentError,
)
from trading_engine.factors import normalized_relative_strength
from trading_engine.fundamentals import (
    fundamental_growth_over_years,
    point_in_time_fundamental,
    point_in_time_price_multiple,
    point_in_time_trailing_pe,
)


router = APIRouter(prefix="/instruments", tags=["instruments"])
_VN_VENUES = {"HOSE", "HNX", "UPCOM"}
_US_VENUES = {"NASDAQ", "NYSE", "NYSE_AMERICAN", "NYSE_ARCA", "CBOE_BZX", "IEX"}


@router.get(
    "/{instrument_id}/history",
    response_model=InstrumentPriceHistoryResponse,
    operation_id="getInstrumentPriceHistory",
)
def instrument_price_history(
    instrument_id: int,
    price_service: Annotated[
        InstrumentAnalysisService, Depends(get_instrument_analysis_service)
    ],
    fundamental_service: Annotated[
        FundamentalService, Depends(get_fundamental_service)
    ],
) -> InstrumentPriceHistoryResponse:
    try:
        stored = price_service.get_stored_history(instrument_id)
    except UnknownInstrumentError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InstrumentPriceUnavailableError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    instrument = stored.instrument
    prices = stored.prices
    is_equity = instrument.instrument_type == "common_stock"
    is_vietnam = is_equity and instrument.venue_code in _VN_VENUES
    benchmark = _relative_strength_benchmark(
        instrument.instrument_type, instrument.venue_code
    )
    relative_strength = pd.Series(index=prices.data.index, dtype=float)
    if benchmark is not None:
        try:
            benchmark_prices = price_service.get_stored_market_index(benchmark).prices
            relative_strength = normalized_relative_strength(
                prices.data["close"], benchmark_prices.data["close"]
            )
        except (UnknownInstrumentError, InstrumentPriceUnavailableError):
            pass

    fundamentals = None
    eps_ttm = pd.Series(index=prices.data.index, dtype=float)
    shares = pd.Series(index=prices.data.index, dtype=float)
    trailing_pe = pd.Series(index=prices.data.index, dtype=float)
    trailing_pb = pd.Series(index=prices.data.index, dtype=float)
    reported_pe = reported_pb = None
    ratio_date = ratio_period = None
    shares_growth = shares_growth_5y = None
    if is_equity:
        try:
            fundamentals = fundamental_service.get_instrument_history(instrument_id)
            snapshots = fundamentals.snapshots
            multiplier = 1000.0 if is_vietnam else 1.0
            eps_ttm = point_in_time_fundamental(
                prices.data.index, snapshots, value_column="eps_ttm", name="eps_ttm"
            )
            shares = point_in_time_fundamental(
                prices.data.index,
                snapshots,
                value_column="shares_outstanding",
                name="shares_outstanding",
            )
            trailing_pe = point_in_time_trailing_pe(
                prices.data["close"], snapshots, price_multiplier=multiplier
            )
            trailing_pb = point_in_time_price_multiple(
                prices.data["close"],
                snapshots,
                value_column="book_value_per_share",
                name="trailing_pb",
                price_multiplier=multiplier,
            )
            as_of = prices.data.index.max()
            shares_growth = fundamental_growth_over_years(
                snapshots, value_column="shares_outstanding", as_of=as_of, years=10
            )
            shares_growth_5y = fundamental_growth_over_years(
                snapshots, value_column="shares_outstanding", as_of=as_of, years=5
            )
            if is_vietnam:
                eligible = snapshots.loc[
                    pd.to_datetime(snapshots["effective_date"], errors="coerce") <= as_of
                ].sort_values("effective_date")
                if not eligible.empty:
                    latest = eligible.iloc[-1]
                    reported_pe = _optional_float(latest.get("reported_pe"))
                    reported_pb = _optional_float(latest.get("reported_pb"))
                    effective = pd.to_datetime(latest.get("effective_date"), errors="coerce")
                    ratio_date = effective.date().isoformat() if not pd.isna(effective) else None
                    period = latest.get("period")
                    ratio_period = str(period) if not pd.isna(period) else None
        except FundamentalsNotFoundError:
            pass

    points = [
        InstrumentPricePointResponse(
            date=timestamp.date().isoformat(),
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=_series_float(row, "volume"),
            eps_ttm=_at(eps_ttm, timestamp),
            shares_outstanding=_at(shares, timestamp),
            trailing_pe=_at(trailing_pe, timestamp),
            trailing_pb=_at(trailing_pb, timestamp),
            relative_strength=_at(relative_strength, timestamp),
        )
        for timestamp, row in prices.data.iterrows()
    ]
    return InstrumentPriceHistoryResponse(
        instrument_id=instrument.id,
        symbol=instrument.symbol,
        instrument_type=instrument.instrument_type,
        venue_code=instrument.venue_code,
        currency=instrument.currency,
        source=stored.price_source,
        price_basis=_display_price_basis(stored.price_basis),
        fetched_at=stored.fetched_at.isoformat(),
        first_date=prices.data.index.min().date().isoformat(),
        last_date=prices.data.index.max().date().isoformat(),
        expected_last_session=stored.expected_last_session,
        is_stale=stored.is_stale,
        row_count=len(points),
        relative_strength_benchmark=benchmark,
        trailing_pe_source=(
            _metadata_source(fundamentals.metadata.sources) if fundamentals else None
        ),
        trailing_pe_method=(
            ", ".join(fundamentals.metadata.methodologies) or None
            if fundamentals else None
        ),
        trailing_pe_fetched_at=(
            fundamentals.metadata.fetched_at.isoformat() if fundamentals else None
        ),
        provider_reported_pe=reported_pe,
        provider_reported_pb=reported_pb,
        provider_ratio_effective_date=ratio_date,
        provider_ratio_period=ratio_period,
        shares_growth_pct=_growth(shares_growth, "total_growth_pct"),
        shares_growth_cagr_pct=_growth(shares_growth, "cagr_pct"),
        shares_growth_observed_years=_growth(shares_growth, "observed_years"),
        shares_growth_start_date=(str(shares_growth["start_date"]) if shares_growth else None),
        shares_growth_full_10y=(bool(shares_growth["full_period"]) if shares_growth else False),
        shares_cagr_5y_pct=_growth(shares_growth_5y, "cagr_pct"),
        shares_cagr_5y_observed_years=_growth(shares_growth_5y, "observed_years"),
        shares_cagr_5y_start_date=(
            str(shares_growth_5y["start_date"]) if shares_growth_5y else None
        ),
        shares_cagr_full_5y=(
            bool(shares_growth_5y["full_period"]) if shares_growth_5y else False
        ),
        prices=points,
    )


def _relative_strength_benchmark(
    instrument_type: str, venue_code: str | None
) -> str | None:
    if instrument_type != "common_stock":
        return None
    if venue_code in _VN_VENUES:
        return "VN30"
    if venue_code in _US_VENUES:
        return "SPX"
    return None


def _at(series: pd.Series, timestamp) -> float | None:
    return (
        float(series.loc[timestamp])
        if timestamp in series.index and not pd.isna(series.loc[timestamp])
        else None
    )


def _series_float(row, key: str) -> float | None:
    value = row.get(key)
    return float(value) if value is not None and not pd.isna(value) else None


def _optional_float(value) -> float | None:
    parsed = pd.to_numeric(value, errors="coerce")
    return float(parsed) if not pd.isna(parsed) else None


def _growth(value, key: str) -> float | None:
    return float(value[key]) if value else None


def _metadata_source(sources: tuple[str, ...]) -> str:
    return sources[0] if len(sources) == 1 else ", ".join(sources)


def _display_price_basis(price_basis: str) -> str:
    return {
        "adjusted": "auto-adjusted OHLC",
        "provider_unspecified": "provider OHLC (adjustment unspecified)",
    }.get(price_basis, price_basis)
