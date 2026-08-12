from __future__ import annotations

import pytest

from api.providers.vietnam_price_loader import VietnamPriceLoader
from scripts import refresh_watchlist_history
from trading_engine.data.yfinance_loader import YFinanceLoader


def test_vn_watchlist_loader_uses_sponsored_provider_and_configured_pacing(
    monkeypatch,
):
    provider = object()
    monkeypatch.setattr(
        refresh_watchlist_history,
        "create_vietnam_market_provider",
        lambda **kwargs: provider,
    )
    monkeypatch.setattr(
        refresh_watchlist_history,
        "provider_runtime_label",
        lambda configured: "vnstock-data-3.2.7-vci",
    )
    monkeypatch.setattr(
        refresh_watchlist_history,
        "env_float",
        lambda name, default: 30.0,
    )

    loader, source, delay = refresh_watchlist_history._loader_config("vnstock_data")

    assert isinstance(loader, VietnamPriceLoader)
    assert loader._provider is provider
    assert source == "vnstock-data-3.2.7-vci"
    assert delay == 2.0


def test_us_watchlist_loader_remains_yfinance():
    loader, source, delay = refresh_watchlist_history._loader_config("yfinance")

    assert isinstance(loader, YFinanceLoader)
    assert source == "yfinance"
    assert delay == 0.0


def test_vn_watchlist_loader_rejects_invalid_request_rate(monkeypatch):
    monkeypatch.setattr(
        refresh_watchlist_history,
        "create_vietnam_market_provider",
        lambda **kwargs: object(),
    )
    monkeypatch.setattr(
        refresh_watchlist_history,
        "env_float",
        lambda name, default: 0.0,
    )

    with pytest.raises(ValueError, match="must be greater than zero"):
        refresh_watchlist_history._loader_config("vnstock_data")
