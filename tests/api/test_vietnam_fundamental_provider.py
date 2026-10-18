from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pandas as pd

from api.providers import vietnam_fundamentals


def test_provider_uses_public_quant_api_with_explicit_vci_source(monkeypatch):
    dataset = object()
    calls: list[tuple[str, object]] = []

    class Dataset:
        @staticmethod
        def load(symbol, **kwargs):
            calls.append(("load", (symbol, kwargs)))
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

    module = SimpleNamespace(Dataset=Dataset, fa=Fa)
    monkeypatch.setattr(vietnam_fundamentals, "import_module", lambda name: module)
    monkeypatch.setattr(
        vietnam_fundamentals.metadata,
        "version",
        lambda package: {"vnstock": "5.1.0", "vnstock-quant": "0.4.0"}[package],
    )
    acquired_at = datetime(2026, 10, 18, 5, 30, tzinfo=UTC)

    result = vietnam_fundamentals.VnstockFundamentalProvider(
        clock=lambda: acquired_at
    ).fetch("fpt")

    assert calls == [
        (
            "load",
            (
                "FPT",
                {
                    "period": "quarter",
                    "prices": True,
                    "notes": False,
                    "source": "vci",
                },
            ),
        ),
        (
            "ratios",
            (
                dataset,
                {
                    "period": "quarter",
                    "profile": "vn",
                    "format": "long",
                },
            ),
        ),
    ]
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
