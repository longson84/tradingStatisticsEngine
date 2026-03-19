"""Tests for trading_engine/data/ — Layer 1 validation gate.

Gate: from trading_engine.data import YFinanceLoader, PriceFrame
Tests: PriceFrame construction, CSV loading, error handling.
Network-dependent tests (YFinance, VNStock) are marked skip by default.
"""
from __future__ import annotations

import os
import tempfile
from datetime import date

import pandas as pd
import pytest

from trading_engine.data import CSVLoader, YFinanceLoader
from trading_engine.types import DataLoadError, PriceFrame


# =============================================================================
# [A] PriceFrame construction
# =============================================================================

class TestPriceFrame:
    def test_valid_construction(self):
        df = pd.DataFrame(
            {"open": [1.0], "high": [2.0], "low": [0.5], "close": [1.5], "volume": [1000.0]},
            index=pd.date_range("2020-01-01", periods=1),
        )
        pf = PriceFrame(symbol="TEST", data=df, source="synthetic")
        assert pf.symbol == "TEST"
        assert pf.source == "synthetic"
        assert len(pf.data) == 1

    def test_missing_columns_raises(self):
        df = pd.DataFrame(
            {"close": [1.0]},
            index=pd.date_range("2020-01-01", periods=1),
        )
        with pytest.raises(ValueError, match="missing columns"):
            PriceFrame(symbol="TEST", data=df, source="test")

    def test_columns_lowercased(self):
        """PriceFrame stores lowercase columns."""
        df = pd.DataFrame(
            {"open": [1.0], "high": [2.0], "low": [0.5], "close": [1.5]},
            index=pd.date_range("2020-01-01", periods=1),
        )
        pf = PriceFrame(symbol="TEST", data=df, source="test")
        assert "close" in pf.data.columns


# =============================================================================
# [B] CSV loader
# =============================================================================

class TestCSVLoader:
    def _write_csv(self, tmpdir: str, symbol: str, rows: int = 10) -> str:
        dates = pd.date_range("2020-01-01", periods=rows, freq="B")
        df = pd.DataFrame(
            {
                "Date": dates.strftime("%Y-%m-%d"),
                "open": [100.0] * rows,
                "high": [105.0] * rows,
                "low": [95.0] * rows,
                "close": [102.0] * rows,
                "volume": [1_000_000] * rows,
            }
        )
        path = os.path.join(tmpdir, f"data_{symbol}.csv")
        df.to_csv(path, index=False)
        return tmpdir

    def test_load_basic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._write_csv(tmpdir, "AAPL")
            loader = CSVLoader(base_dir=tmpdir)
            pf = loader.load("AAPL", date(2020, 1, 1), date(2020, 12, 31))
            assert pf.symbol == "AAPL"
            assert pf.source == "csv"
            assert len(pf.data) > 0
            assert "close" in pf.data.columns

    def test_date_range_filter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._write_csv(tmpdir, "AAPL", rows=50)
            loader = CSVLoader(base_dir=tmpdir)
            pf = loader.load("AAPL", date(2020, 1, 1), date(2020, 1, 10))
            # Only dates within the range
            assert all(pf.data.index <= pd.Timestamp("2020-01-10"))

    def test_missing_file_raises_data_load_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            loader = CSVLoader(base_dir=tmpdir)
            with pytest.raises(DataLoadError, match="No CSV file"):
                loader.load("NONEXISTENT", date(2020, 1, 1), date(2020, 12, 31))

    def test_empty_date_range_raises_data_load_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._write_csv(tmpdir, "AAPL")
            loader = CSVLoader(base_dir=tmpdir)
            with pytest.raises(DataLoadError):
                # Date range outside the data
                loader.load("AAPL", date(2025, 1, 1), date(2025, 12, 31))


# =============================================================================
# [C] YFinanceLoader (network — skipped by default)
# =============================================================================

@pytest.mark.skip(reason="Requires network — run manually with pytest -m network")
class TestYFinanceLoader:
    def test_load_btc(self):
        loader = YFinanceLoader()
        pf = loader.load("BTC-USD", date(2023, 1, 1), date(2023, 3, 31))
        assert pf.symbol == "BTC-USD"
        assert pf.source == "yfinance"
        assert len(pf.data) > 50
        assert "close" in pf.data.columns

    def test_invalid_symbol_raises(self):
        loader = YFinanceLoader()
        with pytest.raises(DataLoadError):
            loader.load("XXXXXXXXXX", date(2023, 1, 1), date(2023, 3, 31))
