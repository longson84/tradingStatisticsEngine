"""Tests for api/routes/factors.py factory wiring."""
from __future__ import annotations

import pytest

from api.routes.factors import _build_factor
from trading_engine.factors import (
    AHR999,
    BollingerBands,
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
        assert isinstance(_build_factor("bollinger", 20, "sma", 2.0), BollingerBands)
        assert isinstance(_build_factor("donchian", 20, "sma"), DonchianChannel)
        assert isinstance(_build_factor("distance_from_peak", 200, "sma"), DistanceFromPeak)

    def test_unknown_factor_still_rejected(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            _build_factor("nonsense", 10, "sma")
