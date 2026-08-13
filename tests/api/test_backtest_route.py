from __future__ import annotations

from datetime import UTC, date, datetime

import numpy as np
import pandas as pd
import pytest
from fastapi import HTTPException

from api.routes.backtest import analyze_single_ticker
from api.schemas.backtest import AnalyzeRequest, PriceVsMAConfig
from api.repositories.instrument_analysis_repository import AnalysisInstrumentRecord
from api.services.instrument_analysis_service import (
    InstrumentPriceData,
    InstrumentPriceUnavailableError,
    UnknownInstrumentError,
)
from trading_engine.types import PriceFrame


class StubInstrumentAnalysisService:
    def __init__(self, result: InstrumentPriceData | Exception):
        self.result = result
        self.calls: list[int] = []

    def get_stored_history(self, instrument_id: int) -> InstrumentPriceData:
        self.calls.append(instrument_id)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _request(**overrides) -> AnalyzeRequest:
    values = {
        "instrument_id": 42,
        "strategy": PriceVsMAConfig(ma_length=20, buy_lag=0, sell_lag=2),
    }
    values.update(overrides)
    return AnalyzeRequest(**values)


def _stored_prices() -> InstrumentPriceData:
    index = pd.date_range("2024-01-02", periods=300, freq="B")
    close = 100 + np.linspace(0, 30, len(index)) + np.sin(np.arange(len(index)) / 5) * 5
    frame = pd.DataFrame(
        {
            "open": close,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": 1_000_000.0,
        },
        index=index,
    )
    return InstrumentPriceData(
        instrument=AnalysisInstrumentRecord(
            id=42,
            symbol="MSFT",
            instrument_type="common_stock",
            company_id=1,
            company_name="Microsoft Corporation",
            venue_code="NASDAQ",
            venue_name="Nasdaq",
            base_asset=None,
            quote_asset=None,
            currency="USD",
            price_basis="adjusted",
            price_source="yfinance",
            first_date=index[0].date(),
            last_date=index[-1].date(),
            stored_sessions=len(index),
        ),
        prices=PriceFrame(symbol="MSFT", data=frame, source="yfinance"),
        expected_last_session=index[-1].date(),
        data_last_session=index[-1].date(),
        is_stale=False,
        price_source="yfinance",
        price_basis="adjusted",
        fetched_at=datetime(2026, 8, 12, tzinfo=UTC),
    )


def test_analyze_request_rejects_reversed_date_range():
    with pytest.raises(ValueError):
        _request(start=date(2025, 1, 1), end=date(2024, 1, 1))


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (UnknownInstrumentError("Unknown instrument"), 404),
        (InstrumentPriceUnavailableError("No stored history"), 422),
    ],
)
def test_analyze_maps_company_price_errors(error: Exception, status: int):
    service = StubInstrumentAnalysisService(error)

    with pytest.raises(HTTPException) as raised:
        analyze_single_ticker(_request(), service)

    assert raised.value.status_code == status
    assert service.calls == [42]


def test_analyze_uses_stored_history_and_preserves_coverage_metadata():
    service = StubInstrumentAnalysisService(_stored_prices())

    result = analyze_single_ticker(
        _request(start=date(2024, 6, 3)),
        service,
    )

    assert service.calls == [42]
    assert result.symbol == "MSFT"
    assert result.from_date >= "2024-06-03"
    assert result.instrument_id == 42
    assert result.venue_code == "NASDAQ"
    assert result.price_source == "yfinance"
    assert result.price_basis == "adjusted"
    assert result.is_stale is False
