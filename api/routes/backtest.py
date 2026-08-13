"""Exact-instrument strategy analysis endpoint."""
from __future__ import annotations

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from trading_engine.performance.strategy_analysis import run_single_ticker_analysis
from trading_engine.types import PriceFrame

from api.deps import (
    build_strategy,
    get_instrument_analysis_service,
)
from api.services.instrument_analysis_service import (
    InstrumentAnalysisService,
    InstrumentPriceUnavailableError,
    UnknownInstrumentError,
)
from api.schemas.backtest import (
    AnalyzeRequest,
    SingleTickerAnalysisResponse,
)

router = APIRouter(prefix="/backtest", tags=["backtest"])


@router.post("/analyze", response_model=SingleTickerAnalysisResponse)
def analyze_single_ticker(
    req: AnalyzeRequest,
    price_service: Annotated[
        InstrumentAnalysisService, Depends(get_instrument_analysis_service)
    ],
) -> SingleTickerAnalysisResponse:
    """Full analytics for a single-ticker strategy: performance, trades, heatmaps, health."""
    try:
        stored = price_service.get_current_history(req.instrument_id)
    except UnknownInstrumentError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InstrumentPriceUnavailableError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    symbol = stored.instrument.symbol
    frame = stored.prices.data
    if req.start is not None:
        frame = frame.loc[frame.index.date >= req.start]
    if req.end is not None:
        frame = frame.loc[frame.index.date <= req.end]
    if frame.empty:
        raise HTTPException(
            status_code=422,
            detail=f"No stored price history for {symbol} in the requested date range",
        )
    prices = {
        symbol: PriceFrame(
            symbol=symbol,
            data=frame.copy(),
            source=stored.prices.source,
        )
    }

    strategy = build_strategy(req.strategy)
    strategy_label = f"{req.strategy.type.replace('_', ' ').title()} — {symbol}"

    analysis = run_single_ticker_analysis(
        strategy=strategy,
        symbol=symbol,
        prices=prices,
        initial_capital=req.initial_capital,
        strategy_label=strategy_label,
    )

    return SingleTickerAnalysisResponse(
        **asdict(analysis),
        instrument_id=stored.instrument.id,
        venue_code=stored.instrument.venue_code,
        expected_last_session=stored.expected_last_session,
        data_last_session=stored.data_last_session,
        refreshed=stored.refreshed,
        is_stale=stored.is_stale,
        refresh_warning=stored.refresh_warning,
        price_source=stored.price_source,
        price_basis=stored.price_basis,
    )
