from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pandas as pd
import pytest

from api.providers import vietnam_market


def _ohlcv() -> pd.DataFrame:
    return pd.DataFrame({
        "time": pd.to_datetime(["2026-08-07 07:00:00"]),
        "open": [71.1],
        "high": [71.7],
        "low": [70.3],
        "close": [70.8],
        "volume": [4_301_800],
    })


def _trade_history() -> pd.DataFrame:
    return pd.DataFrame({
        "trading_date": pd.to_datetime(["2026-08-07"]),
        "matched_volume": [4_319_872.0],
        "deal_volume": [40_679.0],
    })


class _SponsoredEquity:
    def ohlcv(self, **kwargs):
        return _ohlcv()

    def trade_history(self, **kwargs):
        return _trade_history()


class _Market:
    def equity(self, symbol: str):
        assert symbol == "FPT"
        return _SponsoredEquity()


def test_sponsored_provider_returns_frames_with_dynamic_provenance(monkeypatch):
    module = SimpleNamespace(Market=_Market)
    monkeypatch.setattr(vietnam_market, "import_module", lambda name: module)
    monkeypatch.setattr(vietnam_market, "_package_version", lambda name: "3.2.7")
    provider = vietnam_market.VnstockDataProvider()

    ohlcv = provider.ohlcv(
        "fpt", date(2026, 8, 1), date(2026, 8, 8)
    )
    trades = provider.trade_history(
        "fpt", date(2026, 8, 1), date(2026, 8, 8)
    )

    assert ohlcv.frame.equals(_ohlcv())
    assert trades.frame.equals(_trade_history())
    assert ohlcv.metadata.package == "vnstock_data"
    assert ohlcv.metadata.package_version == "3.2.7"
    assert ohlcv.metadata.access_mode == "sponsored"
    assert ohlcv.metadata.upstream_source == "unified"


def test_factory_does_not_silently_downgrade_when_sponsor_is_required(monkeypatch):
    monkeypatch.setattr(vietnam_market.util, "find_spec", lambda name: None)

    with pytest.raises(
        vietnam_market.ProviderUnavailableError,
        match="official sponsor installer",
    ):
        vietnam_market.create_vietnam_market_provider(require_sponsored=True)


def test_community_trade_history_is_explicitly_unsupported():
    provider = vietnam_market.CommunityVnstockProvider()

    with pytest.raises(
        vietnam_market.UnsupportedProviderMethodError,
        match="requires the sponsored",
    ):
        provider.trade_history("FPT", date(2026, 8, 1), date(2026, 8, 8))
