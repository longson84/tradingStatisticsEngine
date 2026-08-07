from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest
from fastapi import HTTPException

from api.routes.backtest import analyze_single_ticker
from api.schemas.backtest import AnalyzeRequest, PriceVsMAConfig
from api.services.company_price_service import (
    CompanyPriceData,
    CompanyPriceUnavailableError,
    UnknownCompanyError,
)
from trading_engine.types import PriceFrame


class StubCompanyPriceService:
    def __init__(self, result: CompanyPriceData | Exception):
        self.result = result
        self.calls: list[tuple[str, str]] = []

    def get_current_history(self, market: str, ticker: str) -> CompanyPriceData:
        self.calls.append((market, ticker))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _request(**overrides) -> AnalyzeRequest:
    values = {
        "market": "US",
        "ticker": "MSFT",
        "strategy": PriceVsMAConfig(ma_length=20, buy_lag=0, sell_lag=2),
    }
    values.update(overrides)
    return AnalyzeRequest(**values)


def _stored_prices() -> CompanyPriceData:
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
    return CompanyPriceData(
        prices=PriceFrame(symbol="MSFT", data=frame, source="yfinance"),
        market="US",
        expected_last_session=index[-1].date(),
        data_last_session=index[-1].date(),
        refreshed=False,
        is_stale=False,
        refresh_warning=None,
        price_source="yfinance",
        price_basis="adjusted",
    )


def test_analyze_request_rejects_reversed_date_range():
    with pytest.raises(ValueError):
        _request(start=date(2025, 1, 1), end=date(2024, 1, 1))


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (UnknownCompanyError("Unknown company"), 404),
        (CompanyPriceUnavailableError("No stored history"), 422),
    ],
)
def test_analyze_maps_company_price_errors(error: Exception, status: int):
    service = StubCompanyPriceService(error)

    with pytest.raises(HTTPException) as raised:
        analyze_single_ticker(_request(), service)

    assert raised.value.status_code == status
    assert service.calls == [("US", "MSFT")]


def test_analyze_uses_stored_history_and_preserves_refresh_metadata():
    service = StubCompanyPriceService(_stored_prices())

    result = analyze_single_ticker(
        _request(start=date(2024, 6, 3)),
        service,
    )

    assert service.calls == [("US", "MSFT")]
    assert result.symbol == "MSFT"
    assert result.from_date >= "2024-06-03"
    assert result.market == "US"
    assert result.price_source == "yfinance"
    assert result.price_basis == "adjusted"
    assert result.refreshed is False
    assert result.is_stale is False
