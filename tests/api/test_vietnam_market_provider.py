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


class _Equity:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def ohlcv(self, **kwargs):
        self.calls.append(("ohlcv", kwargs))
        return _ohlcv()

    def trade_history(self, **kwargs):
        self.calls.append(("trade_history", kwargs))
        return _trade_history()


class _Market:
    def __init__(self, equity: _Equity) -> None:
        self._equity = equity
        self.symbols: list[str] = []

    def equity(self, symbol: str):
        self.symbols.append(symbol)
        return self._equity


def test_provider_uses_explicit_vci_routes_and_provenance(monkeypatch):
    equity = _Equity()
    market = _Market(equity)
    module = SimpleNamespace(Market=lambda: market)
    monkeypatch.setattr(vietnam_market, "import_module", lambda name: module)
    monkeypatch.setattr(vietnam_market, "_package_version", lambda name: "5.1.0")
    provider = vietnam_market.VnstockProvider()

    ohlcv = provider.ohlcv(
        "fpt", date(2026, 10, 1), date(2026, 10, 18), interval="1D"
    )
    trades = provider.trade_history(
        "fpt", date(2026, 10, 1), date(2026, 10, 18)
    )

    assert market.symbols == ["FPT", "FPT"]
    assert equity.calls == [
        (
            "ohlcv",
            {
                "start": "2026-10-01",
                "end": "2026-10-18",
                "interval": "1D",
                "source": "vci",
            },
        ),
        (
            "trade_history",
            {
                "start": "2026-10-01",
                "end": "2026-10-18",
                "source": "vci",
            },
        ),
    ]
    assert ohlcv.frame.equals(_ohlcv())
    assert trades.frame.equals(_trade_history())
    assert ohlcv.metadata.package == "vnstock"
    assert ohlcv.metadata.package_version == "5.1.0"
    assert ohlcv.metadata.access_mode == "sponsored"
    assert ohlcv.metadata.upstream_source == "VCI"
    assert vietnam_market.provider_source_label(ohlcv.metadata) == (
        "vnstock-5.1.0-vci"
    )

    normalized = vietnam_market.normalize_ohlcv_result(ohlcv)
    assert normalized["symbol"].tolist() == ["FPT"]
    assert normalized["date"].dt.date.tolist() == [date(2026, 8, 7)]
    assert normalized["provider_source"].tolist() == ["vnstock-5.1.0-vci"]


def test_provider_refuses_an_older_vnstock_runtime(monkeypatch):
    monkeypatch.setattr(vietnam_market, "_package_version", lambda name: "4.0.5")

    with pytest.raises(
        vietnam_market.ProviderUnavailableError,
        match="requires vnstock 5.1.x",
    ):
        vietnam_market.VnstockProvider()


def test_provider_does_not_relabel_market_constructor_errors(monkeypatch):
    class BrokenMarket:
        def __init__(self) -> None:
            raise AttributeError("internal constructor failure")

    module = SimpleNamespace(Market=BrokenMarket)
    monkeypatch.setattr(vietnam_market, "import_module", lambda name: module)
    monkeypatch.setattr(vietnam_market, "_package_version", lambda name: "5.1.0")
    provider = vietnam_market.VnstockProvider()

    with pytest.raises(AttributeError, match="internal constructor failure"):
        provider.ohlcv("FPT", date(2026, 10, 1), date(2026, 10, 18))


def test_module_has_no_generation_specific_provider_exports():
    assert not hasattr(vietnam_market, "VnstockDataProvider")
    assert not hasattr(vietnam_market, "Vnstock5Provider")
