"""Tests for FastAPI dependency wiring."""
from __future__ import annotations

from api.deps import get_loader
from api.providers.vietnam_price_loader import VietnamPriceLoader


def test_get_loader_returns_sponsored_vietnam_loader():
    loader = get_loader("vnstock")

    assert isinstance(loader, VietnamPriceLoader)
