"""Tests for local market-history cache management endpoints."""
from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from fastapi import HTTPException

from api.market_data_jobs import MarketDataJob
from api.repositories.price_bar_repository import PriceBarStatusRecord
from api.repositories.fundamental_repository import FundamentalStatusRecord
from api.routes import market_data
from api.services.price_storage_service import PriceMarketClearResult


class StubPriceStorageService:
    def __init__(self, status: PriceBarStatusRecord | None = None):
        self.status = status
        self.cleared: str | None = None

    def get_status(self, universe: str) -> PriceBarStatusRecord | None:
        return self.status

    def clear_market_for_universe(self, universe: str) -> PriceMarketClearResult:
        self.cleared = universe
        return PriceMarketClearResult(
            market="VN",
            affected_universes=("VN100", "VN30"),
            deleted_rows=42,
        )


class StubFundamentalService:
    def __init__(self, status: FundamentalStatusRecord | None = None):
        self.status = status

    def get_universe_status(self, universe: str) -> FundamentalStatusRecord | None:
        return self.status


def test_cache_status_reads_postgresql_summary(monkeypatch):
    service = StubPriceStorageService(PriceBarStatusRecord(
        universe="US100",
        market="US",
        fetched_at=datetime(2026, 8, 1, tzinfo=UTC),
        first_date=date(2021, 1, 1),
        last_date=date(2026, 7, 31),
        symbol_count=100,
        row_count=125_000,
        sources=("yfinance",),
        price_basis="adjusted",
    ))
    monkeypatch.setattr(market_data, "get_latest_job", lambda universe, dataset="prices": None)
    fundamental_service = StubFundamentalService(FundamentalStatusRecord(
        universe="US100",
        market="US",
        fetched_at=datetime(2026, 8, 2, tzinfo=UTC),
        first_effective_date=date(2010, 1, 1),
        last_effective_date=date(2026, 7, 31),
        symbol_count=99,
        report_count=7_619,
        fact_count=12_022,
        valuation_count=0,
        sources=("yfinance",),
    ))

    result = market_data._cache_status("US100", service, fundamental_service)

    assert result.exists is True
    assert result.last_date == "2026-07-31"
    assert result.symbol_count == 100
    assert result.row_count == 125_000
    assert result.source == "yfinance"
    assert result.price_basis == "auto-adjusted OHLC"
    assert result.fundamentals_exists is True
    assert result.fundamentals_symbol_count == 99
    assert result.fundamentals_snapshot_count == 7_619
    assert result.fundamentals_fetched_at == "2026-08-02T00:00:00+00:00"


def test_market_data_status_includes_us500(monkeypatch):
    monkeypatch.setattr(
        market_data,
        "_cache_status",
        lambda universe, price_service, fundamental_service: market_data.MarketDataCacheStatus(
            universe=universe,
            exists=False,
        ),
    )

    result = market_data.market_data_status(
        StubPriceStorageService(), StubFundamentalService()
    )

    assert [market.universe for market in result.markets] == [
        "US500",
        "US2000",
        "US100",
        "VN100",
        "VN30",
    ]
    assert result.fundamentals_storage == "PostgreSQL"


def test_refresh_market_data_returns_background_job(monkeypatch):
    job = MarketDataJob(id="job-1", market="VN100", mode="incremental")
    monkeypatch.setattr(
        market_data,
        "start_refresh_job",
        lambda market, mode, dataset="prices": job,
    )

    result = market_data.refresh_market_data("vn100", "incremental", "prices")

    assert result.id == "job-1"
    assert result.market == "VN100"
    assert result.status == "queued"


def test_refresh_market_data_rejects_duplicate_job(monkeypatch):
    def duplicate(market, mode, dataset="prices"):
        raise RuntimeError("already running")

    monkeypatch.setattr(market_data, "start_refresh_job", duplicate)
    with pytest.raises(HTTPException) as exc_info:
        market_data.refresh_market_data("US100", "full", "prices")
    assert exc_info.value.status_code == 409


def test_clear_market_data_clears_shared_market_rows(monkeypatch):
    service = StubPriceStorageService()
    monkeypatch.setattr(market_data, "get_active_job", lambda universe: None)
    cleared_jobs: list[str] = []
    monkeypatch.setattr(market_data, "clear_job_history", cleared_jobs.append)

    result = market_data.clear_market_data("vn100", service)

    assert result.cleared is True
    assert result.market == "VN"
    assert result.deleted_rows == 42
    assert result.affected_universes == ["VN100", "VN30"]
    assert service.cleared == "VN100"
    assert cleared_jobs == ["VN100", "VN30"]
