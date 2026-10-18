from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pandas as pd
import pytest

from api import fundamental_provider
from api.providers.vietnam_fundamentals import (
    VietnamFundamentalMetadata,
    VietnamFundamentalResult,
)
from api.providers.vietnam_market import ProviderDataError


def test_fetch_provider_fundamentals_selects_market_source(monkeypatch):
    frame = pd.DataFrame({"effective_date": pd.to_datetime(["2026-05-01"])})
    monkeypatch.setattr(
        fundamental_provider,
        "_fetch_us_fundamentals",
        lambda symbol: (frame, f"US {symbol}"),
    )
    monkeypatch.setattr(
        fundamental_provider,
        "_fetch_vn_fundamentals",
        lambda symbol, provider=None: (frame, "vci", f"VN {symbol}"),
    )

    us_frame, us_source, us_method = (
        fundamental_provider.fetch_provider_fundamentals("aapl", "yfinance")
    )
    vn_frame, vn_source, vn_method = (
        fundamental_provider.fetch_provider_fundamentals("fpt", "vnstock")
    )

    assert us_frame is frame
    assert (us_source, us_method) == ("yfinance", "US AAPL")
    assert vn_frame is frame
    assert (vn_source, vn_method) == ("vci", "VN FPT")


def test_merge_provider_rows_prefers_new_non_null_values():
    existing = pd.DataFrame({
        "effective_date": pd.to_datetime(["2026-05-01"]),
        "period_end": pd.to_datetime(["2026-03-31"]),
        "period": ["2026-Q1"],
        "eps_ttm": [5.0],
        "book_value_per_share": [20.0],
    })
    fetched = pd.DataFrame({
        "effective_date": pd.to_datetime(["2026-05-01"]),
        "period_end": pd.to_datetime(["2026-03-31"]),
        "period": ["2026-Q1"],
        "eps_ttm": [5.5],
        "book_value_per_share": [pd.NA],
    })

    merged = fundamental_provider.merge_fundamentals(existing, fetched)

    assert merged["eps_ttm"].tolist() == [5.5]
    assert merged["book_value_per_share"].tolist() == [20.0]


def _result(ratios: pd.DataFrame, acquired_at) -> VietnamFundamentalResult:
    return VietnamFundamentalResult(
        ratios=ratios,
        acquired_at=acquired_at,
        metadata=VietnamFundamentalMetadata(
            package="vnstock",
            package_version="5.1.0",
            quant_package="vnstock-quant",
            quant_package_version="0.4.0",
            access_mode="sponsored",
            upstream_source="VCI",
            method="quarterly_quant_ratios",
            symbol="FPT",
        ),
    )


def _ratio_rows(period: str, *, complete: bool = True) -> list[dict[str, object]]:
    values = {
        "RT_VALUE_PE": 10.0,
        "RT_VALUE_PB": 2.0,
        "RT_VALUE_PS": 1.25,
        "RT_VALUE_EV_EBITDA": 8.0,
        "RT_VALUE_MARKET_CAP": 1_000.0,
        "RT_VALUE_OUTSTANDING_SHARES": 100.0,
        "RT_VALUE_EPS": 1.0,
        "RT_VALUE_BVPS": 5.0,
        "RT_VALUE_EQUITY": 500.0,
        "RT_PRT_ROE": 0.2,
        "RT_PRT_ROA": 0.1,
        "RT_PRT_GROSS_MARGIN": 0.4,
        "RT_PRT_EBIT_MARGIN": 0.2,
        "RT_PRT_NET_MARGIN": 0.1,
        "RT_LQD_CR": 1.5,
        "RT_LQD_QR": 1.1,
        "RT_LEV_LOAN_EQUITY": 0.3,
    }
    if not complete:
        values.pop("RT_VALUE_PB")
    return [
        {
            "symbol": "FPT",
            "period": period,
            "id": ratio_id,
            "value": value,
            "unit": "ratio",
            "reason": None,
        }
        for ratio_id, value in values.items()
    ]


def test_quant_ratios_select_latest_complete_period_and_map_values():
    ratios = pd.DataFrame([
        *_ratio_rows("2026-Q1"),
        *_ratio_rows("2026-Q2", complete=False),
        *_ratio_rows("2026-Q3"),
    ])
    acquired_at = datetime(
        2026, 10, 18, 10, 0, tzinfo=timezone(timedelta(hours=7))
    )

    frame = fundamental_provider._normalize_vn_quant_ratios(
        _result(ratios, acquired_at)
    )

    assert frame["period"].tolist() == ["2026-Q3"]
    assert frame["period_end"].dt.strftime("%Y-%m-%d").tolist() == ["2026-09-30"]
    assert frame["effective_date"].dt.strftime("%Y-%m-%d").tolist() == [
        "2026-10-19"
    ]
    row = frame.iloc[0]
    assert row["eps_ttm"] == 1.0
    assert row["book_value_per_share"] == 5.0
    assert row["market_cap"] == 1_000.0
    assert row["shares_outstanding"] == 100.0
    assert row["revenue_ttm"] == 800.0
    assert row["gross_profit_ttm"] == 320.0
    assert row["operating_income_ttm"] == 160.0
    assert row["net_income_ttm"] == 100.0
    assert pd.isna(row["total_assets"])
    assert row["total_debt"] == 150.0


def test_quant_ratios_reject_periods_without_required_identity():
    ratios = pd.DataFrame(_ratio_rows("2026-Q2", complete=False))

    with pytest.raises(ProviderDataError, match="complete quarterly ratio"):
        fundamental_provider._normalize_vn_quant_ratios(
            _result(ratios, datetime(2026, 10, 18, tzinfo=UTC))
        )


def test_quant_ratios_reject_missing_acquisition_timestamp():
    ratios = pd.DataFrame(_ratio_rows("2026-Q2"))

    with pytest.raises(ProviderDataError, match="acquisition timestamp"):
        fundamental_provider._normalize_vn_quant_ratios(_result(ratios, None))
