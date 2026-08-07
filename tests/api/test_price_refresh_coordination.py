from __future__ import annotations

import pytest

from api.price_refresh_coordination import (
    acquire_price_refresh,
    get_active_price_refresh,
    release_price_refresh,
)


def test_refresh_lease_blocks_same_market_but_not_other_market():
    acquire_price_refresh("US", "us-owner", "US500")
    try:
        assert get_active_price_refresh("US").label == "US500"
        with pytest.raises(RuntimeError, match="US500"):
            acquire_price_refresh("US", "other-us-owner", "watchlist Leaders")

        acquire_price_refresh("VN", "vn-owner", "VN100")
        release_price_refresh("VN", "vn-owner")
    finally:
        release_price_refresh("US", "us-owner")


def test_only_owner_can_release_refresh_lease():
    acquire_price_refresh("VN", "owner", "VN100")
    try:
        release_price_refresh("VN", "not-owner")
        with pytest.raises(RuntimeError, match="VN100"):
            acquire_price_refresh("VN", "second-owner", "VN30")
    finally:
        release_price_refresh("VN", "owner")
