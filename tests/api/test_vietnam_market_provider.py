from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pandas as pd
import pytest

from api.providers import vietnam_market


SESSION_STATISTIC_CODES = (
    "average_match_volume", "average_match_value", "average_deal_volume",
    "average_deal_value", "average_volume", "average_value",
    "total_match_volume", "total_match_value", "total_deal_volume",
    "total_deal_value", "total_volume", "total_value",
    "fr_buy_volume_total", "fr_buy_value_total", "fr_sell_volume_total",
    "fr_sell_value_total", "fr_net_volume_total", "fr_net_value_total",
    "fr_buy_volume_matched", "fr_buy_value_matched",
    "fr_sell_volume_matched", "fr_sell_value_matched",
    "fr_buy_volume_deal", "fr_buy_value_deal", "fr_sell_volume_deal",
    "fr_sell_value_deal", "fr_buy_volume_total_avg",
    "fr_buy_value_total_avg", "fr_sell_volume_total_avg",
    "fr_sell_value_total_avg", "fr_net_volume_total_avg",
    "fr_net_value_total_avg", "fr_buy_volume_matched_avg",
    "fr_buy_value_matched_avg", "fr_sell_volume_matched_avg",
    "fr_sell_value_matched_avg", "fr_buy_volume_deal_avg",
    "fr_buy_value_deal_avg", "fr_sell_volume_deal_avg",
    "fr_sell_value_deal_avg", "fr_net_volume_matched",
    "fr_net_value_matched", "fr_net_volume_matched_avg",
    "fr_net_value_matched_avg", "fr_net_volume_deal", "fr_net_value_deal",
    "fr_net_volume_deal_avg", "fr_net_value_deal_avg",
    "total_buy_trade_volume", "total_sell_trade_volume",
    "total_buy_trade_volume_avg", "total_sell_trade_volume_avg",
    "total_buy_trade", "total_sell_trade", "total_buy_trade_avg",
    "total_sell_trade_avg", "total_buy_unmatched_volume_avg",
    "total_sell_unmatched_volume_avg", "total_buy_unmatched_volume",
    "total_sell_unmatched_volume", "total_net_trade_volume",
    "total_net_trade_volume_avg", "average_buy_volume_per_trade",
    "average_sell_volume_per_trade",
)


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


def _foreign_flow() -> pd.DataFrame:
    return pd.DataFrame({
        "time": [pd.Timestamp("2026-10-16T00:00:00+07:00")],
        "buy_vol": [1_390_717.0],
        "buy_val": [81_156_580_000.0],
        "sell_vol": [568_508.0],
        "sell_val": [33_224_080_000.0],
        "net_vol": [822_209.0],
        "net_val": [47_932_500_000.0],
    })


def _session_stats() -> pd.DataFrame:
    values = {code: [float(index)] for index, code in enumerate(
        SESSION_STATISTIC_CODES, 1
    )}
    values["fr_net_value_total"] = [-123.25]
    values["fr_net_volume_deal"] = [0.0]
    return pd.DataFrame({"symbol": ["FPT"], **values})


class _Equity:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def ohlcv(self, **kwargs):
        self.calls.append(("ohlcv", kwargs))
        return _ohlcv()

    def trade_history(self, **kwargs):
        self.calls.append(("trade_history", kwargs))
        return _trade_history()

    def foreign_flow(self, **kwargs):
        self.calls.append(("foreign_flow", kwargs))
        return _foreign_flow()

    def proprietary_flow(self, **kwargs):
        self.calls.append(("proprietary_flow", kwargs))
        return _foreign_flow()

    def session_stats(self, **kwargs):
        self.calls.append(("session_stats", kwargs))
        return _session_stats()


class _Market:
    def __init__(self, equity: _Equity) -> None:
        self._equity = equity
        self.calls: list[tuple[str, str]] = []

    def equity(self, symbol: str):
        self.calls.append(("equity", symbol))
        return self._equity

    def index(self, symbol: str):
        self.calls.append(("index", symbol))
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

    assert market.calls == [("equity", "FPT"), ("equity", "FPT")]
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


def test_provider_routes_market_indices_through_index_api(monkeypatch):
    index = _Equity()
    market = _Market(index)
    module = SimpleNamespace(Market=lambda: market)
    monkeypatch.setattr(vietnam_market, "import_module", lambda name: module)
    monkeypatch.setattr(vietnam_market, "_package_version", lambda name: "5.1.0")

    result = vietnam_market.VnstockProvider().ohlcv(
        "VN30",
        date(2026, 10, 16),
        date(2026, 10, 17),
        interval="1D",
        instrument_kind="index",
    )

    assert market.calls == [("index", "VN30")]
    assert index.calls == [("ohlcv", {
        "start": "2026-10-16",
        "end": "2026-10-17",
        "interval": "1D",
        "source": "vci",
    })]
    assert result.metadata.symbol == "VN30"


def test_provider_calls_foreign_flow_with_explicit_vci_source(monkeypatch):
    equity = _Equity()
    market = _Market(equity)
    monkeypatch.setattr(
        vietnam_market,
        "import_module",
        lambda name: SimpleNamespace(Market=lambda: market),
    )
    monkeypatch.setattr(vietnam_market, "_package_version", lambda name: "5.1.0")

    result = vietnam_market.VnstockProvider().foreign_flow(
        "fpt", date(2026, 10, 1), date(2026, 10, 18)
    )

    assert market.calls == [("equity", "FPT")]
    assert equity.calls == [("foreign_flow", {
        "start": "2026-10-01",
        "end": "2026-10-18",
        "source": "vci",
    })]
    assert result.frame.equals(_foreign_flow())
    assert result.metadata.method == "foreign_flow"


def test_provider_calls_proprietary_flow_with_explicit_vci_source(monkeypatch):
    equity = _Equity()
    market = _Market(equity)
    monkeypatch.setattr(
        vietnam_market,
        "import_module",
        lambda name: SimpleNamespace(Market=lambda: market),
    )
    monkeypatch.setattr(vietnam_market, "_package_version", lambda name: "5.1.0")

    result = vietnam_market.VnstockProvider().proprietary_flow(
        "fpt", date(2026, 10, 1), date(2026, 10, 18)
    )

    assert equity.calls == [("proprietary_flow", {
        "start": "2026-10-01",
        "end": "2026-10-18",
        "source": "vci",
    })]
    assert result.frame.equals(_foreign_flow())
    assert result.metadata.method == "proprietary_flow"


def test_provider_calls_session_stats_with_exact_period_and_vci(monkeypatch):
    equity = _Equity()
    market = _Market(equity)
    monkeypatch.setattr(
        vietnam_market,
        "import_module",
        lambda name: SimpleNamespace(Market=lambda: market),
    )
    monkeypatch.setattr(vietnam_market, "_package_version", lambda name: "5.1.0")

    result = vietnam_market.VnstockProvider().session_stats(
        "fpt", date(2026, 10, 15), date(2026, 10, 16)
    )

    assert market.calls == [("equity", "FPT")]
    assert equity.calls == [("session_stats", {
        "start": "2026-10-15",
        "end": "2026-10-16",
        "source": "vci",
    })]
    assert result.frame.equals(_session_stats())
    assert result.metadata.method == "session_stats"


def test_session_statistic_catalog_and_normalizer_are_strict_and_exact():
    from api.session_statistics import (
        SESSION_STATISTIC_METRICS,
        SESSION_STATISTIC_SCHEMA_VERSION,
    )

    assert SESSION_STATISTIC_SCHEMA_VERSION == 1
    assert tuple(metric.code for metric in SESSION_STATISTIC_METRICS) == (
        SESSION_STATISTIC_CODES
    )
    assert {metric.group for metric in SESSION_STATISTIC_METRICS} == {
        "market_activity", "foreign_activity", "trade_direction",
        "order_imbalance",
    }
    assert {metric.unit for metric in SESSION_STATISTIC_METRICS} == {
        "volume", "value", "count",
    }

    result = _flow_result(_session_stats())
    normalized = vietnam_market.normalize_session_stats_result(result)

    assert tuple(normalized) == SESSION_STATISTIC_CODES
    assert normalized["average_match_volume"] == Decimal("1.0")
    assert normalized["fr_net_value_total"] == Decimal("-123.25")
    assert normalized["fr_net_volume_deal"] == Decimal("0.0")


@pytest.mark.parametrize(
    "frame",
    [
        _session_stats().iloc[0:0],
        pd.concat([_session_stats(), _session_stats()], ignore_index=True),
        _session_stats().assign(symbol="VNM"),
        _session_stats().drop(columns=["total_value"]),
        _session_stats().assign(unexpected=1),
        _session_stats().assign(total_value=float("nan")),
        _session_stats().assign(total_value=float("inf")),
        _session_stats().assign(total_value="invalid"),
    ],
)
def test_session_stats_normalizer_rejects_malformed_provider_frames(
    frame: pd.DataFrame,
):
    with pytest.raises(vietnam_market.ProviderDataError, match="session_stats"):
        vietnam_market.normalize_session_stats_result(_flow_result(frame))


def test_session_stats_normalizer_rejects_duplicate_columns():
    frame = _session_stats()
    frame.columns = [*frame.columns[:-1], frame.columns[-2]]

    with pytest.raises(vietnam_market.ProviderDataError, match="session_stats"):
        vietnam_market.normalize_session_stats_result(_flow_result(frame))


def _flow_result(frame: pd.DataFrame) -> vietnam_market.VietnamProviderResult:
    return vietnam_market.VietnamProviderResult(
        frame=frame,
        metadata=vietnam_market.VietnamProviderMetadata(
            package="vnstock",
            package_version="5.1.0",
            access_mode="sponsored",
            upstream_source="VCI",
            method="foreign_flow",
            symbol="FPT",
            requested_start=date(2026, 10, 1),
            requested_end=date(2026, 10, 18),
        ),
    )


def test_foreign_flow_normalization_maps_gen5_columns_and_vietnam_dates():
    normalized = vietnam_market.normalize_foreign_flow_result(
        _flow_result(_foreign_flow())
    )

    assert normalized.columns.tolist() == [
        "symbol", "date", "buy_volume", "buy_value", "sell_volume",
        "sell_value", "net_volume", "net_value", "provider_source",
    ]
    assert normalized.loc[0, "date"] == date(2026, 10, 16)
    assert normalized.loc[0, "buy_volume"] == 1_390_717.0
    assert normalized.loc[0, "provider_source"] == "vnstock-5.1.0-vci"


def test_proprietary_flow_normalization_uses_shared_strict_daily_schema():
    result = _flow_result(_foreign_flow())
    result = vietnam_market.VietnamProviderResult(
        frame=result.frame,
        metadata=vietnam_market.VietnamProviderMetadata(
            **{**result.metadata.__dict__, "method": "proprietary_flow"}
        ),
    )

    normalized = vietnam_market.normalize_proprietary_flow_result(result)

    assert normalized.columns.tolist() == [
        "symbol", "date", "buy_volume", "buy_value", "sell_volume",
        "sell_value", "net_volume", "net_value", "provider_source",
    ]
    assert normalized.loc[0, "date"] == date(2026, 10, 16)
    assert normalized.loc[0, "net_value"] == 47_932_500_000.0


def test_foreign_flow_normalization_keeps_provider_net_values_and_last_duplicate():
    frame = pd.concat([_foreign_flow(), _foreign_flow()], ignore_index=True)
    frame.loc[0, "net_val"] = 123.0
    frame.loc[1, "net_val"] = 456.0
    frame.loc[1, "buy_val"] = 900.0
    frame.loc[1, "sell_val"] = 100.0

    normalized = vietnam_market.normalize_foreign_flow_result(_flow_result(frame))

    assert len(normalized) == 1
    assert normalized.loc[0, "net_value"] == 456.0
    assert normalized.loc[0, "net_value"] != (
        normalized.loc[0, "buy_value"] - normalized.loc[0, "sell_value"]
    )


@pytest.mark.parametrize(
    "frame",
    [
        _foreign_flow().drop(columns=["net_val"]),
        _foreign_flow().assign(buy_val="not-a-number"),
        _foreign_flow().assign(time="not-a-date"),
    ],
)
def test_foreign_flow_normalization_rejects_missing_or_non_numeric_required_values(
    frame: pd.DataFrame,
):
    with pytest.raises(vietnam_market.ProviderDataError, match="foreign_flow"):
        vietnam_market.normalize_foreign_flow_result(_flow_result(frame))


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("buy_vol", -1.0),
        ("buy_val", -1.0),
        ("sell_vol", -1.0),
        ("sell_val", -1.0),
    ],
)
def test_foreign_flow_normalization_rejects_negative_buy_or_sell_values(
    column: str,
    value: float,
):
    with pytest.raises(vietnam_market.ProviderDataError, match="non-negative"):
        vietnam_market.normalize_foreign_flow_result(
            _flow_result(_foreign_flow().assign(**{column: value}))
        )


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
