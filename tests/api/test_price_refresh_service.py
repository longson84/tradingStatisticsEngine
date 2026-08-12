from __future__ import annotations

from datetime import UTC, date, datetime

import pandas as pd

from api.repositories.price_bar_repository import (
    PriceBarCoverageRecord,
    PriceBarWriteRecord,
    SymbolPriceCoverageRecord,
    PriceRefreshStateRecord,
)
from api.services.price_refresh_service import PriceRefreshAttempt, PriceRefreshService
from api.services.price_refresh_service import PriceRefreshTarget


class FakePriceRefreshRepository:
    def __init__(self):
        self.coverage = (
            PriceBarCoverageRecord(
                instrument_id=1,
                ticker="CURRENT",
                first_date=date(2021, 1, 4),
                last_date=date(2026, 8, 3),
            ),
            PriceBarCoverageRecord(
                instrument_id=2,
                ticker="STALE",
                first_date=date(2021, 1, 4),
                last_date=date(2026, 7, 24),
            ),
        )
        self.writes: tuple[PriceBarWriteRecord, ...] = ()
        self.refresh_states: tuple[PriceRefreshStateRecord, ...] = ()
        self.state_writes = ()

    def list_instrument_coverages(self, instrument_ids, price_basis):
        return tuple(
            SymbolPriceCoverageRecord(
                instrument_id=row.instrument_id,
                ticker=row.ticker,
                first_date=row.first_date,
                last_date=row.last_date,
                row_count=1,
                source="test",
                fetched_at=datetime(2026, 8, 3, tzinfo=UTC),
            )
            for row in self.coverage
            if row.instrument_id in instrument_ids
        )

    def upsert_bars(self, records):
        self.writes = tuple(records)
        return len(self.writes)

    def list_instrument_refresh_states(self, instrument_ids, price_basis):
        return tuple(
            row for row in self.refresh_states
            if row.instrument_id in instrument_ids
        )

    def upsert_refresh_states(self, records):
        self.state_writes = tuple(records)
        return len(self.state_writes)


def test_incremental_plan_uses_database_coverage_and_overlap():
    service = PriceRefreshService(FakePriceRefreshRepository())

    plan = service.plan(
        "US500",
        [
            _target(1, "CURRENT", "yfinance", "adjusted"),
            _target(2, "STALE", "yfinance", "adjusted"),
            _target(3, "MISSING", "yfinance", "adjusted"),
            _target(4, "OVERLAP", "yfinance", "adjusted"),
        ],
        full_start=date(2021, 1, 1),
        end=date(2026, 8, 3),
        mode="incremental",
        already_refreshed={4},
    )

    assert plan.requested_starts == {
        2: date(2026, 7, 17),
        3: date(2021, 1, 1),
    }
    assert plan.reused_instrument_ids == (1, 4)


def test_full_plan_rebuilds_existing_but_skips_prior_universe_overlap():
    service = PriceRefreshService(FakePriceRefreshRepository())

    plan = service.plan(
        "US500",
        [
            _target(1, "CURRENT", "yfinance", "adjusted"),
            _target(4, "OVERLAP", "yfinance", "adjusted"),
        ],
        full_start=date(1900, 1, 1),
        end=date(2026, 8, 3),
        mode="full",
        already_refreshed={4},
    )

    assert plan.requested_starts == {1: date(1900, 1, 1)}
    assert plan.reused_instrument_ids == (4,)


def test_incremental_plan_reuses_symbol_checked_without_new_bar():
    repository = FakePriceRefreshRepository()
    repository.refresh_states = (
        PriceRefreshStateRecord(
            instrument_id=2,
            ticker="STALE",
            price_basis="provider_unspecified",
            attempted_through=date(2026, 8, 3),
            returned_through=date(2026, 7, 24),
            outcome="checked_no_new_bar",
            primary_source="vnstock-kbs",
            selected_source="vnstock-vci",
            detail=None,
            attempted_at=datetime(2026, 8, 3, tzinfo=UTC),
        ),
    )
    service = PriceRefreshService(repository)

    plan = service.plan(
        "VN100",
        [_target(2, "STALE", "vnstock_data", "provider_unspecified")],
        full_start=date(2021, 1, 1),
        end=date(2026, 8, 3),
        mode="incremental",
    )

    assert plan.requested_starts == {}
    assert plan.reused_instrument_ids == (2,)


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
        targets_by_provider_symbol={
            "FPT": _target(10, "FPT", "vnstock_data", "provider_unspecified")
        },
        source="vnstock-vci",
        fetched_at=datetime(2026, 8, 3, tzinfo=UTC),
    )

    assert result.input_rows == 2
    assert result.rejected_rows == 1
    assert result.stored_rows == 1
    assert repository.writes[0].instrument_id == 10
    assert repository.writes[0].currency == "VND"
    assert repository.writes[0].price_scale == 1_000
    assert repository.writes[0].price_basis == "provider_unspecified"


def test_record_attempts_persists_attempted_and_returned_dates_separately():
    repository = FakePriceRefreshRepository()
    service = PriceRefreshService(repository)

    stored = service.record_attempts(
        [PriceRefreshAttempt(
            instrument_id=2,
            price_basis="provider_unspecified",
            attempted_through=date(2026, 8, 3),
            returned_through=date(2026, 7, 31),
            outcome="checked_no_new_bar",
            primary_source="vnstock-kbs",
            selected_source="vnstock-vci",
            attempted_at=datetime(2026, 8, 3, tzinfo=UTC),
            detail="both providers checked",
        )],
    )

    assert stored == 1
    assert repository.state_writes[0].attempted_through == date(2026, 8, 3)
    assert repository.state_writes[0].returned_through == date(2026, 7, 31)
    assert repository.state_writes[0].outcome == "checked_no_new_bar"


def _target(
    instrument_id: int,
    symbol: str,
    adapter: str,
    price_basis: str,
) -> PriceRefreshTarget:
    return PriceRefreshTarget(
        instrument_id=instrument_id,
        canonical_symbol=symbol,
        provider_symbol=symbol,
        price_adapter=adapter,
        price_basis=price_basis,
        currency="VND" if adapter == "vnstock_data" else "USD",
        price_scale=1_000 if adapter == "vnstock_data" else 1,
    )
