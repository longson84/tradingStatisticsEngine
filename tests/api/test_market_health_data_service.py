from __future__ import annotations

from datetime import UTC, date, datetime

import pandas as pd

from api.repositories.price_bar_repository import PriceBarStatusRecord
from api.services.market_health_data_service import MarketHealthDataService


class StubRepository:
    def __init__(self):
        self.query = None

    def get_universe_market(self, universe):
        return "US" if universe == "US2000" else None

    def get_latest_date(self, universe, price_basis):
        assert (universe, price_basis) == ("US2000", "adjusted")
        return date(2026, 7, 31)

    def load_close_matrix(self, query):
        self.query = query
        return pd.DataFrame(
            {"AAA": [10.0, 11.0], "BBB": [20.0, float("nan")]},
            index=pd.to_datetime(["2026-07-30", "2026-07-31"]),
        )

    def get_status(self, universe, price_basis, expected_session):
        return PriceBarStatusRecord(
            universe=universe,
            market="US",
            fetched_at=datetime(2026, 8, 1, tzinfo=UTC),
            first_date=date(2020, 1, 2),
            last_date=date(2026, 7, 31),
            symbol_count=2,
            row_count=3,
            sources=("yfinance",),
            price_basis=price_basis,
        )


def test_service_loads_only_requested_close_range_with_metadata():
    repository = StubRepository()
    service = MarketHealthDataService(repository)

    result = service.get_close_history(
        "us2000", start=date(2026, 7, 30), end=date(2026, 7, 31)
    )

    assert repository.query.universe == "US2000"
    assert repository.query.price_basis == "adjusted"
    assert repository.query.start == date(2026, 7, 30)
    assert repository.query.end == date(2026, 7, 31)
    assert result.metadata.symbol_count == 2
    assert result.metadata.row_count == 3
    assert result.metadata.first_date == date(2026, 7, 30)
    assert result.metadata.last_date == date(2026, 7, 31)
    assert service.get_latest_date("US2000") == date(2026, 7, 31)
