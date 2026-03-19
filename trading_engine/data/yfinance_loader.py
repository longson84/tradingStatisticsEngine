"""YFinance data loader — fetches OHLCV data from Yahoo Finance."""
from __future__ import annotations

from datetime import date

import pandas as pd
import yfinance as yf

from trading_engine.types import DataLoadError, PriceFrame


class YFinanceLoader:
    """Loads historical OHLCV data from Yahoo Finance.

    Implements the DataLoader protocol.
    Retries 2x on timeout, raises DataLoadError after.
    """

    MAX_RETRIES = 2

    def load(self, symbol: str, start: date, end: date) -> PriceFrame:
        last_error: Exception | None = None

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                df = yf.download(
                    symbol,
                    start=start.isoformat(),
                    end=end.isoformat(),
                    progress=False,
                )
                break
            except Exception as e:
                last_error = e
                if attempt < self.MAX_RETRIES:
                    continue
                raise DataLoadError(
                    f"Failed to load {symbol} from yfinance after "
                    f"{self.MAX_RETRIES + 1} attempts: {e}"
                ) from e
        else:
            raise DataLoadError(
                f"Failed to load {symbol} from yfinance: {last_error}"
            )

        # yfinance sometimes returns MultiIndex columns
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        if df.empty:
            raise DataLoadError(f"No data returned for {symbol} from yfinance")

        # Normalize column names to lowercase
        df.columns = df.columns.str.lower()
        df.index.name = "date"

        # Ensure required columns exist
        required = {"open", "high", "low", "close"}
        actual = set(df.columns)
        missing = required - actual
        if missing:
            raise DataLoadError(
                f"yfinance data for {symbol} missing columns: {missing}"
            )

        # Keep only OHLCV columns, drop NaN rows
        keep = [c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]
        df = df[keep].dropna(subset=["open", "high", "low", "close"])

        return PriceFrame(symbol=symbol, data=df, source="yfinance")
