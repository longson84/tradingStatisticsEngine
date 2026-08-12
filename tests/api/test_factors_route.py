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
from api.services.instrument_analysis_service import (
    InstrumentPriceUnavailableError,
    StoredInstrumentPriceSet,
    UnknownInstrumentError,
)
from api.repositories.instrument_analysis_repository import AnalysisInstrumentRecord
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
    """Factor Rarity identifies one canonical instrument."""

    def test_rejects_ahr999_from_general_rarity_workflow(self):
        with pytest.raises(ValueError):
            RarityRequest(instrument_id=1, factor_type="ahr999")

    def test_accepts_distance_from_ma(self):
        req = RarityRequest(
            instrument_id=42,
            factor_type="distance_from_ma",
            period=200,
            ma_type="sma",
        )
        assert req.factor_type == "distance_from_ma"
        assert req.instrument_id == 42

    def test_rejects_non_positive_instrument_id(self):
        with pytest.raises(ValueError):
            RarityRequest(instrument_id=0, factor_type="distance_from_peak")


class RejectingInstrumentPriceService:
    def __init__(self, error: Exception):
        self.error = error

    def get_current_history(self, instrument_id):
        raise self.error


class TestRarityEndpointPriceValidation:
    def test_unknown_instrument_maps_to_not_found(self):
        request = RarityRequest(
            instrument_id=999, factor_type="distance_from_peak"
        )

        with pytest.raises(HTTPException) as raised:
            rarity_analysis_endpoint(
                request,
                RejectingInstrumentPriceService(
                    UnknownInstrumentError("Unknown instrument: 999")
                ),
            )

        assert raised.value.status_code == 404

    def test_missing_stored_history_maps_to_unprocessable(self):
        request = RarityRequest(
            instrument_id=17, factor_type="distance_from_peak"
        )

        with pytest.raises(HTTPException) as raised:
            rarity_analysis_endpoint(
                request,
                RejectingInstrumentPriceService(
                    InstrumentPriceUnavailableError("No stored price history")
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
            description="",
            created_at=datetime(2026, 8, 4, tzinfo=UTC),
            updated_at=datetime(2026, 8, 4, tzinfo=UTC),
            members=(WatchlistMemberRecord(
                instrument_id=42,
                symbol="MSFT",
                instrument_type="common_stock",
                company_id=11,
                company_name="Microsoft",
                sector=None,
                industry=None,
                venue_code=None,
                venue_name=None,
                base_asset=None,
                quote_asset=None,
                currency="USD",
                position=0,
            ),),
        )

        class Watchlists:
            def get_watchlist(self, watchlist_id):
                assert watchlist_id == 7
                return watchlist

        class Prices:
            def get_stored_histories(self, instrument_ids):
                assert instrument_ids == [42]
                instrument = AnalysisInstrumentRecord(
                    id=42,
                    symbol="MSFT",
                    instrument_type="common_stock",
                    company_id=11,
                    company_name="Microsoft",
                    venue_code=None,
                    venue_name=None,
                    base_asset=None,
                    quote_asset=None,
                    currency="USD",
                    price_basis="adjusted",
                    price_source="yfinance",
                    first_date=dates[0].date(),
                    last_date=dates[-1].date(),
                    stored_sessions=len(dates),
                )
                return StoredInstrumentPriceSet(
                    instruments={42: instrument},
                    prices={42: prices},
                    expected_last_sessions={42: dates[-1].date()},
                    data_last_sessions={42: dates[-1].date()},
                    price_sources={42: "yfinance"},
                    missing_instrument_ids=(),
                    stale_instrument_ids=(),
                )

        response = predefined_rarity_endpoint(
            PredefinedRarityRequest(watchlist_id=7),
            Watchlists(),
            Prices(),
        )

        assert response.watchlist_name == "Leaders"
        assert response.requested_instruments == 1
        assert response.available_instruments == 1
        assert response.instruments[0].instrument_id == 42
        assert response.instruments[0].price_basis == "adjusted"
        assert all(table.rows[0].instrument_id == 42 for table in response.tables)
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

        row = _predefined_row(99, "TEST", DistanceFromPeak(window=200), prices)

        assert row.instrument_id == 99
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
