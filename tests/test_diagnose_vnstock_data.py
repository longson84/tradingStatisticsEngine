from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pandas as pd

from scripts import diagnose_vnstock_data


def test_diagnostic_reports_schema_and_coverage_without_credentials(monkeypatch):
    metadata = SimpleNamespace(
        package="vnstock_data",
        package_version="3.2.7",
        access_mode="sponsored",
        symbol="FPT",
    )
    ohlcv = SimpleNamespace(
        frame=pd.DataFrame({
            "time": pd.to_datetime(["2026-08-06", "2026-08-07"]),
            "close": [70.7, 70.8],
        }),
        metadata=metadata,
    )
    trades = SimpleNamespace(
        frame=pd.DataFrame({
            "trading_date": pd.to_datetime(["2026-08-06", "2026-08-07"]),
            "matched_volume": [1.0, 2.0],
        }),
        metadata=metadata,
    )

    class Provider:
        def ohlcv(self, *args, **kwargs):
            return ohlcv

        def trade_history(self, *args, **kwargs):
            return trades

    monkeypatch.setattr(
        diagnose_vnstock_data,
        "VnstockDataProvider",
        Provider,
    )

    result = diagnose_vnstock_data.run_diagnostic(
        "FPT", date(2026, 8, 1), date(2026, 8, 8)
    )

    assert result["authenticated"] is True
    assert result["package_version"] == "3.2.7"
    assert result["ohlcv"]["rows"] == 2
    assert result["trade_history"]["last_date"] == "2026-08-07"
    assert "api_key" not in result
