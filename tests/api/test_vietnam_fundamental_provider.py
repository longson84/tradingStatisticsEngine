from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from api.providers import vietnam_fundamentals


class _Finance:
    def __init__(self, **kwargs):
        assert kwargs == {
            "symbol": "FPT",
            "period": "quarter",
            "get_all": True,
            "show_log": False,
        }

    def _get_report(self, **kwargs):
        assert kwargs["report_type"] == "ratio"
        assert kwargs["mode"] == "raw"
        assert kwargs["get_all"] is True
        return pd.DataFrame({"pe": [10.0]})

    def income_statement(self, **kwargs):
        assert kwargs["mode"] == "raw"
        assert kwargs["get_all"] is True
        return pd.DataFrame({"publicDate": ["2026-04-28"]})


def test_sponsored_fundamental_provider_uses_explicit_vci_adapter(monkeypatch):
    monkeypatch.setattr(
        vietnam_fundamentals,
        "import_module",
        lambda name: SimpleNamespace(Finance=_Finance),
    )
    monkeypatch.setattr(
        vietnam_fundamentals.metadata,
        "version",
        lambda package: "3.2.7",
    )

    result = vietnam_fundamentals.VnstockDataFundamentalProvider().fetch("fpt")

    assert result.metadata.package == "vnstock_data"
    assert result.metadata.package_version == "3.2.7"
    assert result.metadata.upstream_source == "VCI"
    assert vietnam_fundamentals.fundamental_source_label(result.metadata) == "vci"
    assert "vnstock-data 3.2.7" in (
        vietnam_fundamentals.fundamental_methodology(result.metadata)
    )
