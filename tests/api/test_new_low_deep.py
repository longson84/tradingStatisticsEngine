from __future__ import annotations

from datetime import date

import pandas as pd
import pytest
from fastapi import HTTPException

from api.main import app
from api.repositories.instrument_analysis_repository import AnalysisInstrumentRecord
from api.routes.events import new_low_deep_endpoint
from api.schemas.events import NewLowDeepRequest
from api.services.instrument_analysis_service import StoredInstrumentPriceSet
from api.services.new_low_analysis_service import NewLowAnalysisService
from trading_engine.event_analysis import analyze_new_low_episodes
from trading_engine.types import PriceFrame


def _instrument(instrument_id: int = 42) -> AnalysisInstrumentRecord:
    return AnalysisInstrumentRecord(
        id=instrument_id,
        symbol="DUPL",
        instrument_type="common_stock",
        company_id=7,
        company_name="Canonical Company",
        sector="Industrials",
        industry="Industrial Products",
        venue_code="NYSE",
        venue_name="New York Stock Exchange",
        base_asset=None,
        quote_asset=None,
        currency="USD",
        price_basis="adjusted",
        price_source="canonical-test",
        first_date=date(2024, 1, 1),
        last_date=date(2026, 1, 1),
        stored_sessions=320,
        universes=("TEST",),
    )


def _prices() -> PriceFrame:
    dates = pd.date_range("2024-01-01", periods=320, freq="B")
    close = pd.Series(100.0 + (pd.RangeIndex(len(dates)) % 40), index=dates)
    close.iloc[100:120] = pd.Series(
        range(90, 70, -1), index=dates[100:120], dtype=float
    )
    return PriceFrame(
        symbol="DUPL",
        data=pd.DataFrame({
            "open": close,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": 1_000_000.0,
        }),
        source="canonical-test",
    )


class StoredPricesOnly:
    """Deliberately exposes no provider-refresh method."""

    def __init__(self, *, include_instrument: bool = True, include_prices: bool = True):
        self.requested_ids: tuple[int, ...] | None = None
        self.include_instrument = include_instrument
        self.include_prices = include_prices

    def get_stored_histories(self, instrument_ids):
        self.requested_ids = tuple(instrument_ids)
        instrument = _instrument()
        prices = _prices()
        return StoredInstrumentPriceSet(
            instruments={instrument.id: instrument} if self.include_instrument else {},
            prices={instrument.id: prices} if self.include_prices else {},
            expected_last_sessions={instrument.id: date(2026, 1, 5)} if self.include_prices else {},
            data_last_sessions={instrument.id: date(2026, 1, 1)} if self.include_prices else {},
            price_sources={instrument.id: "canonical-test"} if self.include_prices else {},
            missing_instrument_ids=() if self.include_prices else (instrument.id,),
            stale_instrument_ids=(instrument.id,) if self.include_prices else (),
        )


def test_deep_analysis_uses_exact_id_and_preserves_engine_result():
    stored = StoredPricesOnly()
    service = NewLowAnalysisService(stored)

    result = service.analyze_deep(
        42,
        lookback_sessions=50,
        quick_recovery_sessions=2,
        forward_horizons=[5, 20],
    )
    direct = analyze_new_low_episodes(
        _prices(),
        lookback_sessions=50,
        quick_recovery_sessions=2,
        forward_horizons=[5, 20],
    )

    assert stored.requested_ids == (42,)
    assert result.instrument.id == 42
    assert result.instrument.symbol == "DUPL"
    assert result.price_history.price_basis == "adjusted"
    assert result.price_history.source == "canonical-test"
    assert result.price_history.is_stale is True
    assert result.analysis.episodes == direct.episodes
    assert result.analysis.forward_stats == direct.forward_stats


def test_deep_route_serializes_identity_provenance_and_freshness():
    response = new_low_deep_endpoint(
        NewLowDeepRequest(
            instrument_id=42,
            lookback_sessions=50,
            quick_recovery_sessions=2,
            forward_horizons=[5, 20],
        ),
        NewLowAnalysisService(StoredPricesOnly()),
    )

    assert response.formula_version == "new-low-episodes-v1"
    assert response.instrument.id == 42
    assert response.instrument.company_name == "Canonical Company"
    assert response.instrument.venue_code == "NYSE"
    assert response.price_history.source == "canonical-test"
    assert response.price_history.data_last_session == date(2026, 1, 1)
    assert response.price_history.expected_last_session == date(2026, 1, 5)
    assert response.price_history.is_stale is True
    assert response.analysis.symbol == "DUPL"


def test_deep_route_distinguishes_unknown_instrument_from_missing_history():
    with pytest.raises(HTTPException) as unknown:
        new_low_deep_endpoint(
            NewLowDeepRequest(instrument_id=42),
            NewLowAnalysisService(StoredPricesOnly(include_instrument=False, include_prices=False)),
        )
    assert unknown.value.status_code == 404

    with pytest.raises(HTTPException) as missing:
        new_low_deep_endpoint(
            NewLowDeepRequest(instrument_id=42),
            NewLowAnalysisService(StoredPricesOnly(include_prices=False)),
        )
    assert missing.value.status_code == 422
    assert "canonical stored PostgreSQL" in str(missing.value.detail)


def test_deep_request_validates_forward_horizons():
    with pytest.raises(ValueError, match="positive"):
        NewLowDeepRequest(instrument_id=42, forward_horizons=[5, 0])
    with pytest.raises(ValueError, match="unique"):
        NewLowDeepRequest(instrument_id=42, forward_horizons=[5, 5])


def test_deep_openapi_contract_is_exact_instrument_and_legacy_is_retired():
    schema = app.openapi()
    operation = schema["paths"]["/events/new-low-deep"]["post"]
    assert operation["operationId"] == "analyzeNewLowDeep"
    request = schema["components"]["schemas"]["NewLowDeepRequest"]["properties"]
    assert "instrument_id" in request
    assert "symbol" not in request
    assert "symbols" not in request
    assert "data_source" not in request
    assert "date_range" not in request
    assert "/events/new-low-episodes" not in schema["paths"]
