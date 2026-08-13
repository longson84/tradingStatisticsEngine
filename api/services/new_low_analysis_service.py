"""Canonical exact-instrument New-Low Deep analysis use case."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from api.repositories.instrument_analysis_repository import AnalysisInstrumentRecord
from api.services.instrument_analysis_service import (
    InstrumentAnalysisService,
    InstrumentPriceUnavailableError,
    UnknownInstrumentError,
)
from trading_engine.event_analysis import analyze_new_low_episodes
from trading_engine.event_analysis.new_low_episodes import NewLowAnalysisResult


NEW_LOW_DEEP_FORMULA_VERSION = "new-low-episodes-v1"


@dataclass(frozen=True)
class NewLowDeepPriceStatus:
    source: str
    price_basis: str
    first_session: date
    data_last_session: date
    expected_last_session: date
    stored_sessions: int
    is_stale: bool


@dataclass(frozen=True)
class NewLowDeepAnalysisData:
    instrument: AnalysisInstrumentRecord
    price_history: NewLowDeepPriceStatus
    analysis: NewLowAnalysisResult


class NewLowAnalysisService:
    """Analyze only canonical PostgreSQL observations; never refresh providers."""

    def __init__(self, instrument_service: InstrumentAnalysisService) -> None:
        self._instrument_service = instrument_service

    def analyze_deep(
        self,
        instrument_id: int,
        *,
        lookback_sessions: int,
        quick_recovery_sessions: int,
        forward_horizons: list[int],
    ) -> NewLowDeepAnalysisData:
        stored = self._instrument_service.get_stored_histories((instrument_id,))
        instrument = stored.instruments.get(instrument_id)
        if instrument is None:
            raise UnknownInstrumentError(f"Unknown instrument: {instrument_id}")
        prices = stored.prices.get(instrument_id)
        if prices is None:
            raise InstrumentPriceUnavailableError(
                "No canonical stored PostgreSQL price history for "
                f"instrument {instrument.id} ({instrument.symbol})"
            )

        analysis = analyze_new_low_episodes(
            prices=prices,
            lookback_sessions=lookback_sessions,
            quick_recovery_sessions=quick_recovery_sessions,
            forward_horizons=forward_horizons,
        )
        first_session = prices.data.index.min().date()
        data_last_session = stored.data_last_sessions[instrument_id]
        expected_last_session = stored.expected_last_sessions[instrument_id]
        return NewLowDeepAnalysisData(
            instrument=instrument,
            price_history=NewLowDeepPriceStatus(
                source=stored.price_sources[instrument_id],
                price_basis=instrument.price_basis,
                first_session=first_session,
                data_last_session=data_last_session,
                expected_last_session=expected_last_session,
                stored_sessions=len(prices.data),
                is_stale=instrument_id in stored.stale_instrument_ids,
            ),
            analysis=analysis,
        )
