"""CSV data loader — reads OHLCV data from local CSV files."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from trading_engine.types import DataLoadError, PriceFrame


class CSVLoader:
    """Loads historical OHLCV data from a CSV file.

    Implements the DataLoader protocol.
    The CSV must have a 'Date' or 'date' column (or a DatetimeIndex)
    and at minimum: open, high, low, close columns (case-insensitive).
    """

    def __init__(self, base_dir: str | Path):
        self.base_dir = Path(base_dir)

    def load(self, symbol: str, start: date, end: date) -> PriceFrame:
        # Find a CSV file matching the symbol
        pattern = f"*{symbol}*.csv"
        matches = sorted(self.base_dir.glob(pattern))

        if not matches:
            raise DataLoadError(
                f"No CSV file matching '{pattern}' in {self.base_dir}"
            )

        filepath = matches[-1]  # use most recent if multiple
        try:
            df = pd.read_csv(filepath, parse_dates=True)
        except Exception as e:
            raise DataLoadError(f"Failed to read {filepath}: {e}") from e

        # Normalize the index
        date_col = None
        for col in df.columns:
            if col.lower() in ("date", "time", "datetime"):
                date_col = col
                break

        if date_col is not None:
            df[date_col] = pd.to_datetime(df[date_col])
            df = df.set_index(date_col)
        elif not isinstance(df.index, pd.DatetimeIndex):
            raise DataLoadError(
                f"CSV {filepath} has no recognizable date column"
            )

        df.index.name = "date"
        df.columns = df.columns.str.lower()

        # Filter to date range
        df = df.loc[str(start):str(end)]

        if df.empty:
            raise DataLoadError(
                f"No data for {symbol} in date range {start} to {end}"
            )

        keep = [c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]
        df = df[keep].dropna(subset=["open", "high", "low", "close"])

        return PriceFrame(symbol=symbol, data=df, source="csv")
