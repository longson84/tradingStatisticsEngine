"""Tests for api/routes/factors.py factory wiring."""
from __future__ import annotations

import pandas as pd
import pytest

from api.routes.factors import _PREDEFINED_FACTORS, _build_factor, _normalise_symbols, _predefined_row
from api.schemas.factor import PredefinedRarityRequest, RarityRequest
from trading_engine.factors import (
    AHR999,
    BollingerBands,
    DistanceFromMovingAverage,
    DonchianChannel,
    DistanceFromPeak,
    MovingAverageRatio,
)
from trading_engine.types import PriceFrame


class TestBuildFactor:
    def test_ahr999_is_registered(self):
        factor = _build_factor("ahr999", 200, "sma")
        assert isinstance(factor, AHR999)

    def test_existing_factors_unaffected(self):
        assert isinstance(_build_factor("moving_average", 50, "ema"), MovingAverageRatio)
        assert isinstance(_build_factor("distance_from_ma", 50, "ema"), DistanceFromMovingAverage)
        assert isinstance(_build_factor("bollinger", 20, "sma", 2.0), BollingerBands)
        assert isinstance(_build_factor("donchian", 20, "sma"), DonchianChannel)
        assert isinstance(_build_factor("distance_from_peak", 200, "sma"), DistanceFromPeak)

    def test_unknown_factor_still_rejected(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            _build_factor("nonsense", 10, "sma")


class TestRarityRequestSchema:
    """The request schema must accept the same factor types the factory builds.

    If the schema's Literal lacks 'ahr999', FastAPI rejects the request body
    with a 422 (detail is a list of error objects) before _build_factor runs —
    which surfaces in the UI as the unhelpful "[object Object]".
    """

    def test_accepts_ahr999(self):
        req = RarityRequest(
            symbol="BTC-USD",
            date_range={"start": "2000-01-01", "end": "2024-01-01"},
            factor_type="ahr999",
        )
        assert req.factor_type == "ahr999"

    def test_accepts_distance_from_ma(self):
        req = RarityRequest(
            symbol="MSFT",
            date_range={"start": "2000-01-01", "end": "2024-01-01"},
            factor_type="distance_from_ma",
            period=200,
            ma_type="sma",
        )
        assert req.factor_type == "distance_from_ma"


class TestPredefinedRarity:
    def test_request_accepts_symbols_only(self):
        req = PredefinedRarityRequest(symbols=["ko", "MSFT"])

        assert req.symbols == ["ko", "MSFT"]
        assert req.data_source == "yfinance"

    def test_normalise_symbols_dedupes_and_uppercases(self):
        assert _normalise_symbols([" ko ", "MSFT", "ko", "", " msft "]) == ["KO", "MSFT"]

    def test_predefined_factor_set_includes_ma_and_high_windows(self):
        assert [key for key, _, _ in _PREDEFINED_FACTORS] == [
            "distance_ma50",
            "distance_ma100",
            "distance_ma150",
            "distance_ma200",
            "distance_high_100",
            "distance_high_150",
            "distance_high_200",
        ]

    def test_peak_reference_uses_latest_window_close_high(self):
        dates = pd.date_range("2020-01-01", periods=220, freq="B")
        close = pd.Series(100.0, index=dates)
        close.iloc[30] = 500.0
        close.iloc[150] = 300.0
        prices = PriceFrame(
            symbol="TEST",
            data=pd.DataFrame(
                {
                    "open": close,
                    "high": close + 10,
                    "low": close - 10,
                    "close": close,
                    "volume": 1_000_000.0,
                }
            ),
            source="synthetic",
        )

        high_100 = DistanceFromPeak(window=100).context(prices)["peak_price"]
        high_200 = DistanceFromPeak(window=200).context(prices)["peak_price"]

        assert high_100 == pytest.approx(300.0)
        assert high_200 == pytest.approx(500.0)
        assert high_100 <= high_200

    def test_predefined_row_outputs_fixed_percent_columns_in_percentage_units(self):
        dates = pd.date_range("2020-01-01", periods=260, freq="B")
        close = pd.Series(range(100, 360), index=dates, dtype=float)
        prices = PriceFrame(
            symbol="TEST",
            data=pd.DataFrame(
                {
                    "open": close,
                    "high": close,
                    "low": close,
                    "close": close,
                    "volume": 1_000_000.0,
                }
            ),
            source="synthetic",
        )

        row = _predefined_row("TEST", DistanceFromPeak(window=200), prices)

        assert row.symbol == "TEST"
        assert row.observations == 61
        assert row.reference_price == pytest.approx(359.0)
        assert row.p50_price == pytest.approx(359.0)
        assert row.current_price == pytest.approx(359.0)
        assert set(row.percentiles) == {
            "p5",
            "p10",
            "p15",
            "p20",
            "p25",
            "p50",
            "p75",
            "p80",
            "p90",
            "p95",
        }
        assert row.current_value_pct == pytest.approx(0.0)
        assert row.current_percentile == pytest.approx(100.0)
