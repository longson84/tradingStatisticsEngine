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
        "trading_date": [pd.Timestamp("2026-10-16T00:00:00+07:00")],
        "end_trading_date": ["2026-10-16T00:00:00"],
        "market_cap": [100_000_000_000.25],
        "total_shares": [1_000_000.0],
        "ceiling_price": [75_000.0],
        "floor_price": [65_000.0],
        "reference_price": [70_000.0],
        "open": [71_000.0],
        "close": [70_500.0],
        "match_price": [70_500.0],
        "price_change": [-500.0],
        "percent_price_change": [-0.71],
        "high": [72_000.0],
        "low": [69_000.0],
        "average_price": [70_500.0],
        "average_price_adjusted": [70_500.0],
        "matched_volume": [4_319_872.0],
        "matched_value": [300_000_000_000.25],
        "deal_volume": [40_679.0],
        "deal_value": [2_000_000_000.5],
        "total_volume": [4_360_551.0],
        "total_value": [302_000_000_000.75],
        "total_buy_trade": [1_000.0],
        "total_buy_trade_volume": [2_000_000.0],
        "total_sell_trade": [1_100.0],
        "total_sell_trade_volume": [2_360_551.0],
        "reference_price_adjusted": [70_000.0],
        "open_price_adjusted": [71_000.0],
        "close_price_adjusted": [70_500.0],
        "price_change_adjusted": [-500.0],
        "percent_price_change_adjusted": [-0.71],
        "highest_price_adjusted": [72_000.0],
        "lowest_price_adjusted": [69_000.0],
        "total_net_trade_volume": [-360_551.0],
        "total_buy_unmatched_volume": [100.0],
        "total_sell_unmatched_volume": [200.0],
        "price_change_value": ["-500 (-0.71%)"],
        "average_buy_trade_volume": [2_000.125],
        "average_sell_trade_volume": [2_145.955455],
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
                "resolution": "1D",
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


TRADE_STORAGE_COLUMNS = (
    "market_cap", "total_shares", "matched_volume", "matched_value",
    "deal_volume", "deal_value", "total_volume", "total_value",
    "total_buy_trade", "total_buy_trade_volume", "total_sell_trade",
    "total_sell_trade_volume", "total_net_trade_volume",
    "total_buy_unmatched_volume", "total_sell_unmatched_volume",
    "average_buy_trade_volume", "average_sell_trade_volume",
)


def test_trade_history_normalizer_preserves_exact_values_and_approved_columns():
    from api.trade_statistics import (
        TRADE_HISTORY_PROVIDER_COLUMNS,
        TRADE_STATISTIC_SCHEMA_VERSION,
        TRADE_STATISTIC_STORAGE_COLUMNS,
    )

    frame = _trade_history()
    earlier = frame.copy()
    earlier["trading_date"] = "2026-10-15T17:00:00Z"
    earlier["end_trading_date"] = "2026-10-16T00:00:00+07:00"
    later = frame.copy()
    later["trading_date"] = "2026-10-17"
    later["end_trading_date"] = "2026-10-17"
    normalized = vietnam_market.normalize_trade_history_result(
        _flow_result(pd.concat([later, earlier], ignore_index=True))
    )

    assert TRADE_STATISTIC_SCHEMA_VERSION == 1
    assert tuple(frame.columns) == TRADE_HISTORY_PROVIDER_COLUMNS
    assert TRADE_STATISTIC_STORAGE_COLUMNS == TRADE_STORAGE_COLUMNS
    assert tuple(normalized.columns) == (
        "symbol", "trading_date", *TRADE_STORAGE_COLUMNS, "provider_source",
    )
    assert normalized["trading_date"].tolist() == [
        date(2026, 10, 16), date(2026, 10, 17),
    ]
    assert normalized["symbol"].tolist() == ["FPT", "FPT"]
    assert normalized["provider_source"].tolist() == ["vnstock-5.1.0-vci"] * 2
    assert normalized.loc[0, "matched_value"] == Decimal("300000000000.25")
    assert normalized.loc[0, "average_buy_trade_volume"] == Decimal("2000.125")
    assert normalized.loc[0, "total_net_trade_volume"] == Decimal("-360551.0")
    assert all(isinstance(normalized.loc[0, column], Decimal)
               for column in TRADE_STORAGE_COLUMNS)


def test_trade_history_normalizer_accepts_zero_gross_and_signed_net_values():
    frame = _trade_history()
    frame[list(TRADE_STORAGE_COLUMNS)] = 0
    frame["total_net_trade_volume"] = -1

    normalized = vietnam_market.normalize_trade_history_result(_flow_result(frame))

    assert normalized.loc[0, "total_volume"] == Decimal("0")
    assert normalized.loc[0, "total_net_trade_volume"] == Decimal("-1")


def test_trade_history_normalizer_checks_totals_without_decimal_rounding():
    frame = _trade_history().assign(
        matched_value="99999999999999999999999999999999.123456",
        deal_value="0.000001",
        total_value="99999999999999999999999999999999.123457",
    )

    normalized = vietnam_market.normalize_trade_history_result(_flow_result(frame))

    assert normalized.loc[0, "total_value"] == Decimal(
        "99999999999999999999999999999999.123457"
    )


@pytest.mark.parametrize("day", ["2026-09-30", "2026-10-19"])
def test_trade_history_normalizer_rejects_dates_outside_requested_period(day):
    frame = _trade_history().assign(trading_date=day, end_trading_date=day)
    with pytest.raises(vietnam_market.ProviderDataError, match="outside the requested period"):
        vietnam_market.normalize_trade_history_result(_flow_result(frame))


@pytest.mark.parametrize("column", list(_trade_history().columns))
def test_trade_history_normalizer_rejects_missing_columns(column):
    with pytest.raises(vietnam_market.ProviderDataError, match="trade_history"):
        vietnam_market.normalize_trade_history_result(
            _flow_result(_trade_history().drop(columns=[column]))
        )


@pytest.mark.parametrize("frame", [
    _trade_history().assign(unexpected=1),
    pd.concat([_trade_history(), _trade_history()], ignore_index=True),
    _trade_history().assign(trading_date="not-a-date"),
    _trade_history().assign(trading_date=None),
    _trade_history().assign(end_trading_date="not-a-date"),
    _trade_history().assign(end_trading_date="2026-10-17"),
    _trade_history().assign(price_change_value=None),
    _trade_history().assign(price_change_value=""),
    _trade_history().assign(price_change_value=123),
    _trade_history().assign(price_change_value="invalid"),
    _trade_history().assign(total_volume=1),
    _trade_history().assign(total_value=1),
])
def test_trade_history_normalizer_rejects_malformed_provider_frames(frame):
    with pytest.raises(vietnam_market.ProviderDataError, match="trade_history"):
        vietnam_market.normalize_trade_history_result(_flow_result(frame))


def test_trade_history_normalizer_rejects_duplicate_columns():
    frame = _trade_history()
    frame.columns = [*frame.columns[:-1], frame.columns[-2]]
    with pytest.raises(vietnam_market.ProviderDataError, match="trade_history"):
        vietnam_market.normalize_trade_history_result(_flow_result(frame))


@pytest.mark.parametrize("column", [
    column for column in _trade_history().columns
    if column not in {"trading_date", "end_trading_date", "price_change_value"}
])
@pytest.mark.parametrize("value", [float("nan"), float("inf"), "invalid"])
def test_trade_history_normalizer_rejects_invalid_numeric_values(column, value):
    with pytest.raises(vietnam_market.ProviderDataError, match="trade_history"):
        vietnam_market.normalize_trade_history_result(
            _flow_result(_trade_history().assign(**{column: value}))
        )


@pytest.mark.parametrize("column", [
    column for column in TRADE_STORAGE_COLUMNS
    if column != "total_net_trade_volume"
])
def test_trade_history_normalizer_rejects_negative_gross_values(column):
    with pytest.raises(vietnam_market.ProviderDataError, match="non-negative"):
        vietnam_market.normalize_trade_history_result(
            _flow_result(_trade_history().assign(**{column: -1}))
        )


@pytest.mark.parametrize("frame", [None, pd.DataFrame(), _trade_history().iloc[:0]])
def test_trade_history_provider_rejects_empty_responses(monkeypatch, frame):
    equity = SimpleNamespace(trade_history=lambda **kwargs: frame)
    monkeypatch.setattr(vietnam_market, "_package_version", lambda name: "5.1.0")
    monkeypatch.setattr(vietnam_market.VnstockProvider, "_market", lambda self: _Market(equity))

    with pytest.raises(vietnam_market.ProviderDataError, match="no data"):
        vietnam_market.VnstockProvider().trade_history(
            "FPT", date(2026, 10, 1), date(2026, 10, 18)
        )


def test_trade_history_provider_translates_typed_errors_with_safe_context(monkeypatch):
    from vnstock.core.exceptions import VnstockError

    error = VnstockError("credential=super-secret-token")
    error.code = "VNSTOCK_SOURCE_RATE_LIMITED"
    error.action = "Wait and retry."

    def fail(**kwargs):
        raise error

    monkeypatch.setattr(vietnam_market, "_package_version", lambda name: "5.1.0")
    monkeypatch.setattr(
        vietnam_market.VnstockProvider, "_market",
        lambda self: _Market(SimpleNamespace(trade_history=fail)),
    )
    with pytest.raises(vietnam_market.ProviderDataError) as caught:
        vietnam_market.VnstockProvider().trade_history(
            "FPT", date(2026, 10, 1), date(2026, 10, 18)
        )

    assert "VNSTOCK_SOURCE_RATE_LIMITED" in str(caught.value)
    assert "Wait and retry." in str(caught.value)
    assert "super-secret-token" not in str(caught.value)


def test_trade_history_provider_omits_unsafe_error_action(monkeypatch):
    from vnstock.core.exceptions import VnstockError

    error = VnstockError("request failed")
    error.code = "VNSTOCK_AUTH_INVALID"
    error.action = "Retry using api_key=super-secret-token"

    def fail(**kwargs):
        raise error

    monkeypatch.setattr(vietnam_market, "_package_version", lambda name: "5.1.0")
    monkeypatch.setattr(vietnam_market.VnstockProvider, "_market", lambda self: _Market(
        SimpleNamespace(trade_history=fail)
    ))
    with pytest.raises(vietnam_market.ProviderDataError) as caught:
        vietnam_market.VnstockProvider().trade_history(
            "FPT", date(2026, 10, 1), date(2026, 10, 18)
        )

    assert "VNSTOCK_AUTH_INVALID" in str(caught.value)
    assert "super-secret-token" not in str(caught.value)


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
