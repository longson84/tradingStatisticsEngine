"""Tests for api/routes/factors.py factory wiring."""
from __future__ import annotations

import pytest

from api.routes.factors import _build_factor
from api.schemas.factor import RarityRequest
from trading_engine.factors import (
    AHR999,
    BollingerBands,
    DistanceFromMovingAverage,
    DonchianChannel,
    DistanceFromPeak,
    MovingAverageRatio,
)


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
