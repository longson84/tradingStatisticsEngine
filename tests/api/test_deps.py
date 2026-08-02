"""Tests for FastAPI dependency wiring."""
from __future__ import annotations

from api.deps import get_loader
from trading_engine.data.vnstock_loader import VNStockLoader


def test_get_loader_returns_vnstock_loader():
    loader = get_loader("vnstock")

    assert isinstance(loader, VNStockLoader)
