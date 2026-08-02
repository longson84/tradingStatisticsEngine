"""Tests for local market-history cache management endpoints."""
from __future__ import annotations

import json

import pytest
from fastapi import HTTPException

from api.market_data_jobs import MarketDataJob
from api.routes import market_data


def test_cache_status_reads_manifest_and_file_size(tmp_path, monkeypatch):
    (tmp_path / "us100.csv").write_text("symbol,date,close\nA,2026-01-01,1\n")
    (tmp_path / "us100.json").write_text(json.dumps({
        "fetched_at": "2026-08-01T00:00:00+00:00",
        "first_date": "2021-01-01",
        "last_date": "2026-07-31",
        "symbol_count": 100,
        "row_count": 125_000,
        "source": "yfinance",
        "price_basis": "auto-adjusted OHLC",
        "errors": [],
    }))
    monkeypatch.setattr(market_data, "get_latest_job", lambda universe, dataset="prices": None)

    result = market_data._cache_status("US100", tmp_path, tmp_path / "fundamentals")

    assert result.exists is True
    assert result.last_date == "2026-07-31"
    assert result.symbol_count == 100
    assert result.size_bytes == (tmp_path / "us100.csv").stat().st_size


def test_market_data_status_includes_us500(monkeypatch):
    monkeypatch.setattr(
        market_data,
        "_cache_status",
        lambda universe: market_data.MarketDataCacheStatus(
            universe=universe,
            exists=False,
            size_bytes=0,
        ),
    )

    result = market_data.market_data_status()

    assert [market.universe for market in result.markets] == [
        "US500",
        "US2000",
        "US100",
        "VN100",
        "VN30",
    ]


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


def test_clear_market_data_removes_only_selected_cache(tmp_path, monkeypatch):
    for filename in (
        "vn100.csv",
        "vn100.json",
        "vn100.refresh.csv",
        "vn100.refresh.json",
        "us100.csv",
    ):
        (tmp_path / filename).write_text("test")
    monkeypatch.setattr(market_data, "DEFAULT_CACHE_DIR", tmp_path)
    monkeypatch.setattr(market_data, "get_active_job", lambda universe: None)
    monkeypatch.setattr(market_data, "clear_job_history", lambda universe: None)

    result = market_data.clear_market_data("vn100")

    assert result.cleared is True
    assert not list(tmp_path.glob("vn100*"))
    assert (tmp_path / "us100.csv").exists()
