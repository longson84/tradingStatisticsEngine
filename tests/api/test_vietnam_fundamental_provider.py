from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pandas as pd

from api.providers import vietnam_fundamentals


def test_provider_builds_quant_dataset_from_explicit_vci_calls(monkeypatch):
    dataset = object()
    calls: list[tuple[str, object]] = []
    statement = pd.DataFrame({
        "period": ["2026-Q2"], "id": ["IS_NET_PROFIT"], "value": [100.0]
    })
    trade = pd.DataFrame({
        "trading_date": pd.to_datetime(["2026-10-16"]),
        "close": [100.0],
        "total_shares": [1_000.0],
    })

    class EquityFundamental:
        def income_statement(self, *args, **kwargs):
            calls.append(("income_statement", (args, kwargs)))
            return statement

        def balance_sheet(self, *args, **kwargs):
            calls.append(("balance_sheet", (args, kwargs)))
            return statement

        def cash_flow(self, *args, **kwargs):
            calls.append(("cash_flow", (args, kwargs)))
            return statement

    class Fundamental:
        def equity(self, symbol):
            calls.append(("fundamental_equity", symbol))
            return EquityFundamental()

    class EquityMarket:
        def trade_history(self, **kwargs):
            calls.append(("trade_history", kwargs))
            return trade

    class Market:
        def equity(self, symbol):
            calls.append(("market_equity", symbol))
            return EquityMarket()

    class Dataset:
        @staticmethod
        def from_frames(statements, prices):
            calls.append(("from_frames", (statements, prices)))
            return dataset

    class Fa:
        @staticmethod
        def ratios(value, **kwargs):
            calls.append(("ratios", (value, kwargs)))
            return pd.DataFrame({
                "symbol": ["FPT"],
                "period": ["2026-Q2"],
                "id": ["RT_VALUE_PE"],
                "value": [10.0],
                "unit": ["times"],
                "reason": [None],
            })

    modules = {
        "vnstock": SimpleNamespace(Fundamental=Fundamental, Market=Market),
        "vnstock_quant": SimpleNamespace(Dataset=Dataset, fa=Fa),
    }
    monkeypatch.setattr(
        vietnam_fundamentals, "import_module", lambda name: modules[name]
    )
    monkeypatch.setattr(
        vietnam_fundamentals.metadata,
        "version",
        lambda package: {"vnstock": "5.1.0", "vnstock-quant": "0.4.0"}[package],
    )
    acquired_at = datetime(2026, 10, 18, 5, 30, tzinfo=UTC)

    result = vietnam_fundamentals.VnstockFundamentalProvider(
        clock=lambda: acquired_at
    ).fetch("fpt")

    statement_calls = [call for call in calls if call[0] in {
        "income_statement", "balance_sheet", "cash_flow"
    }]
    assert [name for name, _ in statement_calls] == [
        "income_statement", "balance_sheet", "cash_flow"
    ]
    assert all(args == ((None,), {
        "period": "quarter", "source": "vci", "drop_empty": False
    }) for _, args in statement_calls)
    trade_calls = [value for name, value in calls if name == "trade_history"]
    assert trade_calls == [
        {"start": "2017-01-01", "end": "2019-12-31", "source": "vci"},
        {"start": "2020-01-01", "end": "2022-12-31", "source": "vci"},
        {"start": "2023-01-01", "end": "2025-12-31", "source": "vci"},
        {"start": "2026-01-01", "end": "2026-10-18", "source": "vci"},
    ]
    assert calls[-1] == (
        "ratios",
        (dataset, {"period": "quarter", "profile": "vn", "format": "long"}),
    )
    assert result.acquired_at == acquired_at
    assert result.metadata.package == "vnstock"
    assert result.metadata.package_version == "5.1.0"
    assert result.metadata.quant_package == "vnstock-quant"
    assert result.metadata.quant_package_version == "0.4.0"
    assert result.metadata.upstream_source == "VCI"
    assert vietnam_fundamentals.fundamental_source_label(result.metadata) == "vci"
    methodology = vietnam_fundamentals.fundamental_methodology(result.metadata)
    assert "vnstock 5.1.0" in methodology
    assert "vnstock-quant 0.4.0" in methodology


def test_fundamental_request_cost_matches_statement_and_price_fanout():
    assert vietnam_fundamentals.fundamental_request_cost(
        datetime(2026, 10, 18, tzinfo=UTC).date()
    ) == 7
