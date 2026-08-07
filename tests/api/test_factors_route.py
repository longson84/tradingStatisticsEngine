"""Tests for api/routes/factors.py factory wiring."""
from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pytest
from fastapi import HTTPException

from api.routes.factors import (
    _PREDEFINED_FACTORS,
    _build_factor,
    _predefined_row,
    predefined_rarity_endpoint,
    rarity_analysis_endpoint,
)
from api.schemas.factor import PredefinedRarityRequest, RarityRequest
from api.services.company_price_service import (
    StoredCompanyPriceData,
    CompanyPriceUnavailableError,
    UnknownCompanyError,
)
from api.repositories.watchlist_repository import (
    WatchlistMemberRecord,
    WatchlistRecord,
)
from api.services.watchlist_service import UnknownWatchlistError
from trading_engine.factors import (
    AHR999,
    BollingerBands,
    DistanceFromMovingAverage,
    DonchianChannel,
    DistanceFromPeak,
    MovingAverageRatio,
)
from trading_engine.types import PriceFrame


class TestBuildFactor:
    def test_ahr999_is_registered(self):
        factor = _build_factor("ahr999", 200, "sma")
        assert isinstance(factor, AHR999)

    def test_existing_factors_unaffected(self):
        assert isinstance(_build_factor("moving_average", 50, "ema"), MovingAverageRatio)
        assert isinstance(_build_factor("distance_from_ma", 50, "ema"), DistanceFromMovingAverage)
        assert isinstance(_build_factor("bollinger", 20, "sma", 2.0), BollingerBands)
        assert isinstance(_build_factor("donchian", 20, "sma"), DonchianChannel)
        assert isinstance(_build_factor("distance_from_peak", 200, "sma"), DistanceFromPeak)

    def test_unknown_factor_still_rejected(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            _build_factor("nonsense", 10, "sma")


class TestRarityRequestSchema:
    """Company Factor Rarity accepts only canonical market-price factors."""

    def test_rejects_crypto_only_ahr999_from_company_workflow(self):
        with pytest.raises(ValueError):
            RarityRequest(market="US", ticker="MSFT", factor_type="ahr999")

    def test_accepts_distance_from_ma(self):
        req = RarityRequest(
            market="US",
            ticker="MSFT",
            factor_type="distance_from_ma",
            period=200,
            ma_type="sma",
        )
        assert req.factor_type == "distance_from_ma"
        assert req.market == "US"
        assert req.ticker == "MSFT"


class RejectingCompanyPriceService:
    def __init__(self, error: Exception):
        self.error = error

    def get_current_history(self, market, ticker):
        raise self.error


class TestRarityEndpointPriceValidation:
    def test_unknown_company_maps_to_not_found(self):
        request = RarityRequest(
            market="US", ticker="NOT-IN-DB", factor_type="distance_from_peak"
        )

        with pytest.raises(HTTPException) as raised:
            rarity_analysis_endpoint(
                request,
                RejectingCompanyPriceService(
                    UnknownCompanyError("Unknown company: US-NOT-IN-DB")
                ),
            )

        assert raised.value.status_code == 404

    def test_missing_stored_history_maps_to_unprocessable(self):
        request = RarityRequest(
            market="VN", ticker="FPT", factor_type="distance_from_peak"
        )

        with pytest.raises(HTTPException) as raised:
            rarity_analysis_endpoint(
                request,
                RejectingCompanyPriceService(
                    CompanyPriceUnavailableError("No stored price history")
                ),
            )

        assert raised.value.status_code == 422


class TestPredefinedRarity:
    def test_request_accepts_watchlist_only(self):
        req = PredefinedRarityRequest(watchlist_id=12)

        assert req.watchlist_id == 12

    def test_request_rejects_non_positive_watchlist_id(self):
        with pytest.raises(ValueError):
            PredefinedRarityRequest(watchlist_id=0)

    def test_endpoint_reads_watchlist_prices_and_returns_storage_status(self):
        dates = pd.date_range("2024-01-01", periods=260, freq="B")
        close = pd.Series(range(100, 360), index=dates, dtype=float)
        prices = PriceFrame(
            symbol="MSFT",
            data=pd.DataFrame({
                "open": close,
                "high": close,
                "low": close,
                "close": close,
                "volume": 1_000_000.0,
            }),
            source="yfinance",
        )
        watchlist = WatchlistRecord(
            id=7,
            name="Leaders",
            market="US",
            description="",
            created_at=datetime(2026, 8, 4, tzinfo=UTC),
            updated_at=datetime(2026, 8, 4, tzinfo=UTC),
            members=(WatchlistMemberRecord(
                ticker="MSFT",
                company_name="Microsoft",
                market="US",
                sector=None,
                industry=None,
                exchange=None,
                position=0,
            ),),
        )

        class Watchlists:
            def get_watchlist(self, watchlist_id):
                assert watchlist_id == 7
                return watchlist

        class Prices:
            def get_stored_histories(self, market, tickers):
                assert market == "US"
                assert tickers == ["MSFT"]
                return StoredCompanyPriceData(
                    prices={"MSFT": prices},
                    expected_last_session=dates[-1].date(),
                    missing_tickers=(),
                    stale_tickers=(),
                    price_basis="adjusted",
                )

        response = predefined_rarity_endpoint(
            PredefinedRarityRequest(watchlist_id=7),
            Watchlists(),
            Prices(),
        )

        assert response.watchlist_name == "Leaders"
        assert response.market == "US"
        assert response.requested_symbols == 1
        assert response.available_symbols == 1
        assert response.price_basis == "adjusted"
        assert all(table.rows[0].symbol == "MSFT" for table in response.tables)

    def test_endpoint_rejects_unknown_watchlist(self):
        class MissingWatchlists:
            def get_watchlist(self, watchlist_id):
                raise UnknownWatchlistError(f"Unknown watchlist: {watchlist_id}")

        with pytest.raises(HTTPException) as raised:
            predefined_rarity_endpoint(
                PredefinedRarityRequest(watchlist_id=99),
                MissingWatchlists(),
                object(),
            )

        assert raised.value.status_code == 404

    def test_predefined_factor_set_includes_ma_and_high_windows(self):
        assert [key for key, _, _ in _PREDEFINED_FACTORS] == [
            "distance_ma50",
            "distance_ma100",
            "distance_ma150",
            "distance_ma200",
            "distance_high_100",
            "distance_high_150",
            "distance_high_200",
        ]

    def test_peak_reference_uses_latest_window_close_high(self):
        dates = pd.date_range("2020-01-01", periods=220, freq="B")
        close = pd.Series(100.0, index=dates)
        close.iloc[30] = 500.0
        close.iloc[150] = 300.0
        prices = PriceFrame(
            symbol="TEST",
            data=pd.DataFrame(
                {
                    "open": close,
                    "high": close + 10,
                    "low": close - 10,
                    "close": close,
                    "volume": 1_000_000.0,
                }
            ),
            source="synthetic",
        )

        high_100 = DistanceFromPeak(window=100).context(prices)["peak_price"]
        high_200 = DistanceFromPeak(window=200).context(prices)["peak_price"]

        assert high_100 == pytest.approx(300.0)
        assert high_200 == pytest.approx(500.0)
        assert high_100 <= high_200

    def test_predefined_row_outputs_fixed_percent_columns_in_percentage_units(self):
        dates = pd.date_range("2020-01-01", periods=260, freq="B")
        close = pd.Series(range(100, 360), index=dates, dtype=float)
        prices = PriceFrame(
            symbol="TEST",
            data=pd.DataFrame(
                {
                    "open": close,
                    "high": close,
                    "low": close,
                    "close": close,
                    "volume": 1_000_000.0,
                }
            ),
            source="synthetic",
        )

        row = _predefined_row("TEST", DistanceFromPeak(window=200), prices)

        assert row.symbol == "TEST"
        assert row.observations == 61
        assert row.reference_price == pytest.approx(359.0)
        assert row.p50_price == pytest.approx(359.0)
        assert row.current_price == pytest.approx(359.0)
        assert set(row.percentiles) == {
            "p5",
            "p10",
            "p15",
            "p20",
            "p25",
            "p50",
            "p75",
            "p80",
            "p90",
            "p95",
        }
        assert row.current_value_pct == pytest.approx(0.0)
        assert row.current_percentile == pytest.approx(100.0)
