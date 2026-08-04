from __future__ import annotations

from datetime import UTC, date, datetime

import pandas as pd

from api.repositories.price_bar_repository import (
    PriceBarCoverageRecord,
    PriceBarWriteRecord,
)
from api.services.price_refresh_service import PriceRefreshService


class FakePriceRefreshRepository:
    def __init__(self):
        self.coverage = (
            PriceBarCoverageRecord(
                ticker="CURRENT",
                first_date=date(2021, 1, 4),
                last_date=date(2026, 7, 31),
            ),
            PriceBarCoverageRecord(
                ticker="STALE",
                first_date=date(2021, 1, 4),
                last_date=date(2026, 7, 24),
            ),
        )
        self.writes: tuple[PriceBarWriteRecord, ...] = ()

    def get_universe_market(self, universe: str) -> str | None:
        return {"US500": "US", "VN100": "VN"}.get(universe)

    def list_coverage(self, universe: str, price_basis: str):
        return self.coverage

    def upsert_bars(self, records):
        self.writes = tuple(records)
        return len(self.writes)


def test_incremental_plan_uses_database_coverage_and_overlap():
    service = PriceRefreshService(FakePriceRefreshRepository())

    plan = service.plan(
        "US500",
        ["CURRENT", "STALE", "MISSING", "OVERLAP"],
        full_start=date(2021, 1, 1),
        end=date(2026, 8, 3),
        mode="incremental",
        already_refreshed={"OVERLAP"},
    )

    assert plan.requested_starts == {
        "STALE": date(2026, 7, 17),
        "MISSING": date(2021, 1, 1),
    }
    assert plan.reused_symbols == ("CURRENT", "OVERLAP")


def test_full_plan_rebuilds_existing_but_skips_prior_universe_overlap():
    service = PriceRefreshService(FakePriceRefreshRepository())

    plan = service.plan(
        "US500",
        ["CURRENT", "OVERLAP"],
        full_start=date(1900, 1, 1),
        end=date(2026, 8, 3),
        mode="full",
        already_refreshed={"OVERLAP"},
    )

    assert plan.requested_starts == {"CURRENT": date(1900, 1, 1)}
    assert plan.reused_symbols == ("OVERLAP",)


def test_store_frames_normalizes_vn_units_and_rejects_invalid_rows():
    repository = FakePriceRefreshRepository()
    service = PriceRefreshService(repository)
    frame = pd.DataFrame({
        "symbol": ["FPT", "FPT"],
        "date": pd.to_datetime(["2026-07-31", "2026-08-03"]),
        "open": [66.0, 0.0],
        "high": [68.0, 68.0],
        "low": [65.0, 65.0],
        "close": [67.1, 67.0],
        "volume": [1_000_000.0, 1_100_000.0],
    })

    result = service.store_frames(
        "VN100",
        [frame],
        source="vnstock-vci",
        fetched_at=datetime(2026, 8, 3, tzinfo=UTC),
    )

    assert result.input_rows == 2
    assert result.rejected_rows == 1
    assert result.stored_rows == 1
    assert repository.writes[0].market == "VN"
    assert repository.writes[0].ticker == "FPT"
    assert repository.writes[0].currency == "VND"
    assert repository.writes[0].price_scale == 1_000
    assert repository.writes[0].price_basis == "provider_unspecified"
