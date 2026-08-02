from __future__ import annotations

import pandas as pd
import pytest

from api.routes import market_data
from api.symbol_history import load_cached_symbol_history, save_symbol_history
from trading_engine.types import DataLoadError, PriceFrame


def test_symbol_history_cache_round_trip(tmp_path):
    rows = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-02", "2024-01-03"]),
        "open": [10.0, 11.0],
        "high": [12.0, 13.0],
        "low": [9.0, 10.0],
        "close": [11.0, 12.0],
        "volume": [100.0, 200.0],
    })
    manifest = {
        "symbol": "FPT",
        "fetched_at": "2026-08-01T00:00:00+00:00",
        "first_date": "2024-01-02",
        "last_date": "2024-01-03",
        "row_count": 2,
        "source": "vnstock-kbs",
        "price_basis": "provider OHLC (adjustment unspecified)",
    }

    save_symbol_history("FPT", rows, manifest, cache_dir=tmp_path)
    prices, loaded_manifest = load_cached_symbol_history("fpt", cache_dir=tmp_path)

    assert prices.symbol == "FPT"
    assert prices.data["close"].tolist() == [11.0, 12.0]
    assert loaded_manifest == manifest


def test_symbol_history_missing_cache(tmp_path):
    with pytest.raises(DataLoadError, match="Full history cache for FPT is missing"):
        load_cached_symbol_history("FPT", cache_dir=tmp_path)


def test_symbol_price_history_route_uses_local_cache(monkeypatch):
    dates = pd.to_datetime(["2014-01-02", "2024-01-03"])
    prices = PriceFrame(
        symbol="FPT",
        data=pd.DataFrame({
            "open": [10.0, 11.0],
            "high": [12.0, 13.0],
            "low": [9.0, 10.0],
            "close": [11.0, 12.0],
            "volume": [100.0, 200.0],
        }, index=dates),
        source="vnstock-kbs",
    )
    manifest = {
        "universe": "VN100",
        "fetched_at": "2026-08-01T00:00:00+00:00",
        "first_date": "2024-01-02",
        "last_date": "2024-01-03",
        "row_count": 100,
        "source": "vnstock-vci",
        "price_basis": "provider OHLC (adjustment unspecified)",
    }
    monkeypatch.setattr(
        market_data,
        "load_cached_market_symbol",
        lambda universe, symbol: (prices, manifest),
    )
    benchmark = PriceFrame(
        symbol="VN30",
        data=pd.DataFrame(
            {
                "open": [1000.0, 1000.0],
                "high": [1000.0, 1000.0],
                "low": [1000.0, 1000.0],
                "close": [1000.0, 1000.0],
            },
            index=dates,
        ),
        source="vnstock-vci",
    )
    monkeypatch.setattr(
        market_data,
        "load_cached_benchmark",
        lambda symbol: (benchmark, {"source": "vnstock-vci"}),
    )
    monkeypatch.setattr(
        market_data,
        "load_cached_fundamentals",
        lambda symbol, market: (
            pd.DataFrame({
                "effective_date": pd.to_datetime(["2014-01-03", "2019-01-03", "2024-01-03"]),
                "eps_ttm": [500.0, 550.0, 600.0],
                "shares_outstanding": [50_000_000.0, 50_000_000.0, 100_000_000.0],
                "book_value_per_share": [2500.0, 2750.0, 3000.0],
                "reported_pe": [20.0, 21.0, 22.0],
                "reported_pb": [4.0, 4.2, 4.4],
                "period_end": pd.to_datetime(["2013-12-31", "2018-12-31", "2023-12-31"]),
                "period": ["2013-Q4", "2018-Q4", "2023-Q4"],
            }),
            {
                "source": "test-vci",
                "method": "test point-in-time method",
                "fetched_at": "2026-08-01T00:00:00+00:00",
                "fields": ["eps_ttm", "book_value_per_share"],
            },
        ),
    )

    response = market_data.symbol_price_history("fpt", universe="VN100")

    assert response.symbol == "FPT"
    assert response.universe == "VN100"
    assert response.row_count == 2
    assert response.prices[0].date == "2014-01-02"
    assert response.prices[-1].close == 12.0
    assert response.prices[0].trailing_pe is None
    assert response.prices[0].eps_ttm is None
    assert response.prices[-1].eps_ttm == 600.0
    assert response.prices[0].shares_outstanding is None
    assert response.prices[-1].shares_outstanding == 100_000_000.0
    assert response.prices[-1].trailing_pe == 20.0
    assert response.prices[-1].trailing_pb == 4.0
    assert response.relative_strength_benchmark == "VN30"
    assert response.prices[-1].relative_strength == 12.0
    assert response.prices[0].relative_strength == 11.0
    assert response.trailing_pe_source == "test-vci"
    assert response.provider_reported_pe == 22.0
    assert response.provider_reported_pb == 4.4
    assert response.provider_ratio_effective_date == "2024-01-03"
    assert response.provider_ratio_period == "2023-Q4"
    assert response.shares_growth_full_10y is True
    assert response.shares_growth_pct == 100.0
    assert response.shares_growth_cagr_pct == pytest.approx(7.1773, rel=1e-3)
    assert response.shares_cagr_full_5y is True
    assert response.shares_cagr_5y_pct == pytest.approx(14.8698, rel=1e-3)
    assert response.shares_cagr_5y_start_date == "2019-01-03"


def test_vn_symbol_history_does_not_rebase_fundamentals_to_period_end_price(monkeypatch):
    dates = pd.to_datetime(["2026-06-30", "2026-07-31"])
    prices = PriceFrame(
        symbol="PNJ",
        data=pd.DataFrame({
            "open": [63.0, 31.0],
            "high": [63.0, 31.0],
            "low": [63.0, 31.0],
            "close": [63.0, 31.0],
            "volume": [100.0, 200.0],
        }, index=dates),
        source="vnstock-vci",
    )
    monkeypatch.setattr(
        market_data,
        "load_cached_market_symbol",
        lambda universe, symbol: (prices, {
            "source": "vnstock-vci",
            "price_basis": "provider OHLC (adjustment unspecified)",
            "fetched_at": "2026-08-01T00:00:00+00:00",
        }),
    )
    monkeypatch.setattr(
        market_data,
        "load_cached_benchmark",
        lambda symbol: (
            PriceFrame(
                symbol="VN30",
                data=pd.DataFrame(
                    {
                        "open": [1000.0, 1000.0],
                        "high": [1000.0, 1000.0],
                        "low": [1000.0, 1000.0],
                        "close": [1000.0, 1000.0],
                    },
                    index=dates,
                ),
                source="vnstock-vci",
            ),
            {"source": "vnstock-vci"},
        ),
    )
    monkeypatch.setattr(
        market_data,
        "load_cached_fundamentals",
        lambda symbol, market: (
            pd.DataFrame({
                "effective_date": pd.to_datetime(["2026-07-31"]),
                "period_end": pd.to_datetime(["2026-06-30"]),
                "period": ["2026-Q2"],
                "eps_ttm": [5672.965409913],
                "book_value_per_share": [27153.740301781],
                "reported_pe": [5.464514],
                "reported_pb": [1.141648],
            }),
            {
                "source": "vnstock-vci-4.0.5",
                "method": "VCI quarterly RATIO_TTM",
                "fetched_at": "2026-08-02T00:00:00+00:00",
                "fields": ["eps_ttm", "book_value_per_share", "reported_pe", "reported_pb"],
            },
        ),
    )

    response = market_data.symbol_price_history("PNJ", universe="VN100")

    assert response.prices[0].trailing_pe is None
    assert response.prices[-1].trailing_pe == pytest.approx(5.464514)
    assert response.prices[-1].trailing_pb == pytest.approx(1.141648)
    assert response.provider_reported_pe == pytest.approx(5.464514)
    assert response.provider_reported_pb == pytest.approx(1.141648)
