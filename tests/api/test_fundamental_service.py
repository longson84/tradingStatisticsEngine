from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pandas as pd
import pytest

from api.repositories.fundamental_repository import (
    FundamentalFactRecord,
    FundamentalReportRecord,
    FundamentalStatusRecord,
    ProviderValuationRecord,
)
from api.services.fundamental_service import (
    FUNDAMENTAL_COLUMNS,
    FundamentalService,
    FundamentalsNotFoundError,
)


FETCHED_AT = datetime(2026, 8, 3, tzinfo=UTC)


class FakeFundamentalRepository:
    def instrument_exists(self, market: str, ticker: str) -> bool:
        return (market, ticker) in {("VN", "FPT"), ("VN", "EMPTY")}

    def list_reports(self, market: str, ticker: str):
        if ticker == "EMPTY":
            return ()
        return (
            FundamentalReportRecord(
                id=1,
                ticker="FPT",
                market="VN",
                source="vnstock-vci-4.0.5",
                period_end=date(2025, 3, 31),
                period_label="2025-Q1",
                effective_session_date=date(2025, 4, 25),
                fetched_at=FETCHED_AT,
                reporting_currency="VND",
                methodology="VCI normalized point-in-time fundamentals",
            ),
            FundamentalReportRecord(
                id=2,
                ticker="FPT",
                market="VN",
                source="vnstock-vci-4.0.5",
                period_end=date(2025, 6, 30),
                period_label="2025-Q2",
                effective_session_date=date(2025, 7, 25),
                fetched_at=FETCHED_AT,
                reporting_currency="VND",
                methodology="VCI normalized point-in-time fundamentals",
            ),
        )

    def list_facts(self, report_ids: tuple[int, ...]):
        assert report_ids == (1, 2)
        return (
            FundamentalFactRecord(
                report_id=1,
                metric_code="eps_ttm",
                value=Decimal("1000"),
                unit="per_share",
                currency="VND",
                scale=1,
                period_basis="ttm",
                fact_kind="provider_derived",
                calculation_version="vci-4.0.5",
            ),
            FundamentalFactRecord(
                report_id=2,
                metric_code="eps_ttm",
                value=Decimal("1200"),
                unit="per_share",
                currency="VND",
                scale=1,
                period_basis="ttm",
                fact_kind="provider_derived",
                calculation_version="vci-4.0.5",
            ),
        )

    def list_valuations(self, market: str, ticker: str):
        return (
            ProviderValuationRecord(
                effective_session_date=date(2025, 7, 25),
                metric_code="pe",
                value=Decimal("11.25"),
                unit="ratio",
                currency=None,
                scale=1,
                source="vnstock-vci-4.0.5",
                methodology="provider-reported comparison only",
                fetched_at=FETCHED_AT,
            ),
        )

    def get_universe_status(self, universe: str):
        if universe != "VN100":
            return None
        return FundamentalStatusRecord(
            universe="VN100",
            market="VN",
            fetched_at=FETCHED_AT,
            first_effective_date=date(2025, 4, 25),
            last_effective_date=date(2025, 7, 25),
            symbol_count=1,
            report_count=2,
            fact_count=2,
            valuation_count=1,
            sources=("vnstock-vci-4.0.5",),
        )


def test_service_projects_normalized_records_to_existing_wide_contract():
    service = FundamentalService(FakeFundamentalRepository())

    result = service.get_symbol_history("vn", "fpt")

    assert result.market == "VN"
    assert result.ticker == "FPT"
    assert tuple(result.snapshots.columns) == FUNDAMENTAL_COLUMNS
    assert result.snapshots["effective_date"].tolist() == [
        pd.Timestamp("2025-04-25"),
        pd.Timestamp("2025-07-25"),
    ]
    assert result.snapshots["period"].tolist() == ["2025-Q1", "2025-Q2"]
    assert result.snapshots["eps_ttm"].tolist() == [1000.0, 1200.0]
    assert pd.isna(result.snapshots.loc[0, "reported_pe"])
    assert result.snapshots.loc[1, "reported_pe"] == 11.25
    assert result.metadata.snapshot_count == 2
    assert result.metadata.fields == ("eps_ttm", "reported_pe")
    assert result.metadata.sources == ("vnstock-vci-4.0.5",)
    assert result.metadata.methodologies == (
        "VCI normalized point-in-time fundamentals",
        "provider-reported comparison only",
    )


def test_service_rejects_invalid_unknown_and_empty_instruments():
    service = FundamentalService(FakeFundamentalRepository())

    with pytest.raises(FundamentalsNotFoundError, match="valid market"):
        service.get_symbol_history("CA", "SHOP")
    with pytest.raises(FundamentalsNotFoundError, match="Unknown instrument"):
        service.get_symbol_history("US", "MSFT")
    with pytest.raises(FundamentalsNotFoundError, match="No stored fundamentals"):
        service.get_symbol_history("VN", "EMPTY")


def test_service_normalizes_universe_status_lookup():
    service = FundamentalService(FakeFundamentalRepository())

    assert service.get_universe_status(" vn100 ") is not None
    assert service.get_universe_status(" ") is None
