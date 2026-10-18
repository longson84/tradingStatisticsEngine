from __future__ import annotations

import pytest

from api.price_refresh_coordination import (
    acquire_price_refresh,
    release_price_refresh,
)


def test_refresh_lease_blocks_same_adapter_but_not_other_adapter():
    acquire_price_refresh("yfinance", "us-owner", "US500")
    try:
        with pytest.raises(RuntimeError, match="US500"):
            acquire_price_refresh("yfinance", "other-us-owner", "watchlist Leaders")

        acquire_price_refresh("vnstock", "vn-owner", "VN100")
        release_price_refresh("vnstock", "vn-owner")
    finally:
        release_price_refresh("yfinance", "us-owner")


def test_only_owner_can_release_refresh_lease():
    acquire_price_refresh("vnstock", "owner", "VN100")
    try:
        release_price_refresh("vnstock", "not-owner")
        with pytest.raises(RuntimeError, match="VN100"):
            acquire_price_refresh("vnstock", "second-owner", "VN30")
    finally:
        release_price_refresh("vnstock", "owner")


def test_generation_4_adapter_name_is_rejected():
    with pytest.raises(ValueError, match="Unsupported price refresh adapter"):
        acquire_price_refresh("vnstock_data", "legacy-owner", "VN30")
