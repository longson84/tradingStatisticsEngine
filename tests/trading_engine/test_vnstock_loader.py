from __future__ import annotations

from datetime import date

import pandas as pd

from trading_engine.data.vnstock_loader import VNStockLoader


def _frame(day: str, close: float) -> pd.DataFrame:
    return pd.DataFrame({
        "time": pd.to_datetime([day]),
        "open": [close],
        "high": [close],
        "low": [close],
        "close": [close],
        "volume": [1_000.0],
    })


def test_loader_uses_current_kbs_without_fallback(monkeypatch):
    calls: list[str] = []

    class Quote:
        def __init__(self, symbol: str, source: str):
            calls.append(source)

        def history(self, **kwargs):
            return _frame("2026-08-07", 100.0)

    monkeypatch.setattr("vnstock.Quote", Quote)

    result = VNStockLoader(source="KBS").load(
        "FPT", date(2026, 8, 1), date(2026, 8, 8)
    )

    assert calls == ["KBS"]
    assert result.source == "vnstock-kbs"


def test_loader_falls_back_to_newer_vci_history(monkeypatch):
    calls: list[str] = []

    class Quote:
        def __init__(self, symbol: str, source: str):
            self.source = source
            calls.append(source)

        def history(self, **kwargs):
            return (
                _frame("2026-08-06", 99.0)
                if self.source == "KBS"
                else _frame("2026-08-07", 100.0)
            )

    monkeypatch.setattr("vnstock.Quote", Quote)

    result = VNStockLoader(source="KBS").load(
        "FPT", date(2026, 8, 1), date(2026, 8, 8)
    )

    assert calls == ["KBS", "VCI"]
    assert result.source == "vnstock-vci"
    assert result.data.index.max().date() == date(2026, 8, 7)
