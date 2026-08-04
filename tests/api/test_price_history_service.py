from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from api.repositories.price_bar_repository import PriceBarQuery, PriceBarRecord
from api.services.price_history_service import (
    PriceHistoryNotFoundError,
    PriceHistoryService,
    UnknownPriceUniverseError,
)


class FakePriceBarRepository:
    def __init__(self):
        self.queries: list[PriceBarQuery] = []

    def get_universe_market(self, universe: str) -> str | None:
        return {"US500": "US", "VN100": "VN"}.get(universe)

    def get_latest_date(self, universe: str, price_basis: str):
        return date(2026, 7, 31) if universe in {"US500", "VN100"} else None

    def iter_bars(self, query: PriceBarQuery):
        self.queries.append(query)
        rows = (
            PriceBarRecord(
                ticker="FPT",
                market="VN",
                trading_date=trading_date,
                open=close - 1,
                high=close + 1,
                low=close - 2,
                close=close,
                volume=volume,
                currency="VND",
                price_scale=1_000,
                price_basis="provider_unspecified",
                source="VCI",
                fetched_at=datetime(2026, 8, 1, tzinfo=UTC),
            )
            for trading_date, close, volume in (
                (date(2026, 7, 30), 100.0, 1_000.0),
                (date(2026, 7, 31), 103.0, None),
            )
        )
        return tuple(row for row in rows if query.ticker in (None, row.ticker))


def test_symbol_history_builds_price_frame_and_metadata():
    repository = FakePriceBarRepository()
    service = PriceHistoryService(repository)

    result = service.get_symbol_history("vn100", "fpt")

    assert result.universe == "VN100"
    assert result.prices.symbol == "FPT"
    assert result.prices.data["close"].tolist() == [100.0, 103.0]
    assert result.prices.data["volume"].isna().tolist() == [False, True]
    assert result.metadata.row_count == 2
    assert result.metadata.symbol_count == 1
    assert result.metadata.currency == "VND"
    assert result.metadata.price_scale == 1_000
    assert repository.queries[0].price_basis == "provider_unspecified"


def test_universe_history_groups_records_into_price_frames():
    service = PriceHistoryService(FakePriceBarRepository())

    result = service.get_universe_history("VN100")

    assert set(result.prices) == {"FPT"}
    assert result.metadata.first_date == date(2026, 7, 30)
    assert result.metadata.last_date == date(2026, 7, 31)
    assert service.get_latest_date("VN100") == date(2026, 7, 31)


def test_price_history_rejects_unknown_universe_empty_symbol_and_bad_range():
    service = PriceHistoryService(FakePriceBarRepository())

    with pytest.raises(UnknownPriceUniverseError):
        service.get_universe_history("VN30")
    with pytest.raises(PriceHistoryNotFoundError):
        service.get_symbol_history("VN100", " ")
    with pytest.raises(ValueError, match="start date"):
        service.get_universe_history(
            "VN100", start=date(2026, 8, 1), end=date(2026, 7, 31)
        )
