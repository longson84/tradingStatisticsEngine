"""Fundamental-analysis endpoints."""
from __future__ import annotations

from dataclasses import asdict
from datetime import date, timedelta
import logging

from fastapi import APIRouter, HTTPException
import httpx

from api.deps import fetch_prices
from api.schemas.fundamentals import (
    FundamentalRequest,
    FundamentalResponse,
    GrowthAnalysisResponse,
    GrowthAssessmentRequest,
    GrowthAssessmentResponse,
)
from trading_engine.fundamentals.ai_assessment import (
    GrowthAssessmentConfigError,
    GrowthAssessmentProviderError,
)
from trading_engine.fundamentals import assess_growth_numbers, analyze_growth_fundamentals, analyze_sec_fundamentals

router = APIRouter(prefix="/fundamentals", tags=["fundamentals"])
logger = logging.getLogger(__name__)


@router.post("/sec", response_model=FundamentalResponse)
def sec_fundamentals_endpoint(req: FundamentalRequest) -> FundamentalResponse:
    try:
        result = analyze_sec_fundamentals(
            symbol=req.symbol,
            current_year=req.current_year,
            years=req.years,
        )
        _attach_filing_returns(result, req.data_source)
    except (ValueError, TimeoutError, OSError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return FundamentalResponse(**asdict(result))


@router.post("/growth", response_model=GrowthAnalysisResponse)
def growth_fundamentals_endpoint(req: FundamentalRequest) -> GrowthAnalysisResponse:
    try:
        result = analyze_growth_fundamentals(
            symbol=req.symbol,
            current_year=req.current_year,
            years=req.years,
        )
    except (ValueError, TimeoutError, OSError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return GrowthAnalysisResponse(**asdict(result))


@router.post("/growth/assessment", response_model=GrowthAssessmentResponse)
def growth_assessment_endpoint(req: GrowthAssessmentRequest) -> GrowthAssessmentResponse:
    try:
        result = assess_growth_numbers(req.growth)
    except GrowthAssessmentConfigError as exc:
        logger.warning("Growth assessment config error: %s", exc)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except GrowthAssessmentProviderError as exc:
        logger.warning("Growth assessment provider error: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        logger.warning("Growth assessment network error: %s", exc)
        raise HTTPException(status_code=502, detail=f"AI provider network error: {exc}") from exc
    except (KeyError, TypeError) as exc:
        logger.exception("Growth assessment unexpected response handling error")
        raise HTTPException(status_code=502, detail=f"AI provider response handling error: {exc}") from exc

    return GrowthAssessmentResponse(**asdict(result))


def _attach_filing_returns(result, data_source: str) -> None:
    filing_dates = [
        row.filed
        for row in [*result.rows, *result.quarter_rows]
        if row.filed is not None
    ]
    if not filing_dates:
        return

    start = min(filing_dates) - timedelta(days=10)
    end = max(filing_dates) + timedelta(days=5)
    prices = fetch_prices([result.symbol], start, end, data_source)
    price_frame = prices.get(result.symbol)
    if price_frame is None:
        return

    closes = price_frame.data.sort_index()["close"]
    daily_returns = closes.pct_change() * 100
    trading_dates = [idx.date() for idx in closes.index]
    returns_by_date = {
        idx.date(): float(value)
        for idx, value in daily_returns.items()
        if value == value
    }

    for row in [*result.rows, *result.quarter_rows]:
        reaction_date = _reaction_session_date(row.filed, row.filing_timing, trading_dates)
        row.reaction_session_date = reaction_date
        row.filing_return_pct = returns_by_date.get(reaction_date)


def _reaction_session_date(filed: date | None, filing_timing: str | None, trading_dates: list[date]) -> date | None:
    if filed is None:
        return None

    start_after_filed = filing_timing in {None, "after_close"}
    for trading_date in trading_dates:
        if start_after_filed and trading_date > filed:
            return trading_date
        if not start_after_filed and trading_date >= filed:
            return trading_date
    return None
