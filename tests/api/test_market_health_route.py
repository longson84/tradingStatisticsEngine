"""Tests for cached market-health API serialization."""
from __future__ import annotations

from datetime import date

import pandas as pd

from api.routes import market_health
from api.schemas.market_health import MarketHealthRunRequest
from trading_engine.types import PriceFrame


def _cached_market(universe: str):
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
    manifest = {
        "fetched_at": "2026-07-26T00:00:00+00:00",
        "first_date": "2024-01-01",
        "last_date": "2024-11-01",
        "symbol_count": 1,
        "source": f"{universe.lower()}-test",
        "price_basis": "adjusted",
    }
    return prices, manifest


def test_run_market_health_uses_cached_markets_and_custom_weights(monkeypatch):
    calls: list[str] = []

    def fake_load(universe: str):
        calls.append(universe)
        return _cached_market(universe)

    monkeypatch.setattr(market_health, "load_cached_market_history", fake_load)
    result = market_health.run_market_health(
        MarketHealthRunRequest(
            weights={
                "within_10": 1.0,
                "within_20": 0.0,
                "within_30": 0.0,
                "not_below_40": 0.0,
            }
        )
    )

    assert calls == ["US500", "US2000", "US100", "VN100", "VN30"]
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


def test_distribution_drilldown_returns_cached_bucket_members(monkeypatch):
    monkeypatch.setattr(
        market_health,
        "load_cached_market_history",
        lambda universe: _cached_market(universe),
    )

    result = market_health.market_health_distribution(
        "US500",
        date(2024, 11, 1),
        200,
        -10.0,
        None,
    )

    assert result.universe == "US500"
    assert result.window == 200
    assert [stock.symbol for stock in result.stocks] == ["A"]
    assert result.stocks[0].distance == 0.0
