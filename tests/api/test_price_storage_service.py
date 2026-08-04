from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from api.repositories.price_bar_repository import PriceBarStatusRecord
from api.services.price_history_service import UnknownPriceUniverseError
from api.services.price_storage_service import PriceStorageService


class StubRepository:
    def __init__(self):
        self.deleted_market: str | None = None

    def get_universe_market(self, universe: str) -> str | None:
        return {"VN100": "VN", "US100": "US"}.get(universe)

    def get_status(self, universe: str, price_basis: str):
        return PriceBarStatusRecord(
            universe=universe,
            market="VN",
            fetched_at=datetime(2026, 8, 3, tzinfo=UTC),
            first_date=date(2020, 1, 2),
            last_date=date(2026, 8, 3),
            symbol_count=100,
            row_count=1000,
            sources=("vnstock-vci",),
            price_basis=price_basis,
        )

    def list_market_universes(self, market: str) -> tuple[str, ...]:
        return ("VN100", "VN30") if market == "VN" else ("US100",)

    def delete_market_bars(self, market: str) -> int:
        self.deleted_market = market
        return 1_000


def test_status_selects_market_price_basis():
    status = PriceStorageService(StubRepository()).get_status("vn100")

    assert status is not None
    assert status.price_basis == "provider_unspecified"


def test_clear_is_market_scoped_for_overlapping_universes():
    repository = StubRepository()

    result = PriceStorageService(repository).clear_market_for_universe("vn100")

    assert repository.deleted_market == "VN"
    assert result.affected_universes == ("VN100", "VN30")
    assert result.deleted_rows == 1_000


def test_unknown_universe_is_rejected():
    with pytest.raises(UnknownPriceUniverseError):
        PriceStorageService(StubRepository()).get_status("missing")
