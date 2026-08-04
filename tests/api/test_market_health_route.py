"""Tests for cached market-health API serialization."""
from __future__ import annotations

from datetime import UTC, date, datetime

import pandas as pd

from api.routes import market_health
from api.schemas.market_health import MarketHealthRunRequest
from api.services.price_history_service import (
    PriceHistoryMetadata,
    UniversePriceHistory,
)
from trading_engine.types import PriceFrame


def _stored_market(universe: str) -> UniversePriceHistory:
    dates = pd.date_range("2024-01-01", periods=220, freq="B")
    close = pd.Series(100.0, index=dates)
    prices = {
        "A": PriceFrame(
            symbol="A",
            data=pd.DataFrame(
                {
                    "open": close,
                    "high": close,
                    "low": close,
                    "close": close,
                    "volume": 1_000.0,
                }
            ),
            source="cache",
        )
    }
    return UniversePriceHistory(
        universe=universe,
        prices=prices,
        metadata=PriceHistoryMetadata(
            fetched_at=datetime(2026, 7, 26, tzinfo=UTC),
            first_date=date(2024, 1, 1),
            last_date=date(2024, 11, 1),
            symbol_count=1,
            row_count=220,
            sources=(f"{universe.lower()}-test",),
            price_basis="adjusted",
            currency="USD",
            price_scale=1,
        ),
    )


class StubPriceHistoryService:
    def __init__(self):
        self.calls: list[str] = []

    def get_latest_date(self, universe: str) -> date:
        return date(2024, 11, 1)

    def get_universe_history(self, universe: str, **kwargs) -> UniversePriceHistory:
        self.calls.append(universe)
        return _stored_market(universe)


def test_run_market_health_uses_database_service_and_custom_weights():
    service = StubPriceHistoryService()
    result = market_health.run_market_health(
        MarketHealthRunRequest(
            weights={
                "within_10": 1.0,
                "within_20": 0.0,
                "within_30": 0.0,
                "not_below_40": 0.0,
            }
        ),
        service,
    )

    assert service.calls == ["US500", "US2000", "US100", "VN100", "VN30"]
    assert [market.universe for market in result.markets] == [
        "US500",
        "US2000",
        "US100",
        "VN100",
        "VN30",
    ]
    assert result.markets[0].current.health_score == 100.0
    assert result.markets[0].regime == "strong_stable"
    assert result.markets[0].cache.source == "us500-test"
    assert result.markets[0].distribution[0].label == "0 to -10%"
    assert result.markets[0].distribution[0].count == 1


def test_distribution_drilldown_returns_database_bucket_members():
    result = market_health.market_health_distribution(
        "US500",
        StubPriceHistoryService(),
        date_value=date(2024, 11, 1),
        window=200,
        min_distance=-10.0,
        max_distance=None,
    )

    assert result.universe == "US500"
    assert result.window == 200
    assert [stock.symbol for stock in result.stocks] == ["A"]
    assert result.stocks[0].distance == 0.0
