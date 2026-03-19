"""VNStock data loader — fetches OHLCV data from Vietnamese stock market."""
from __future__ import annotations

from datetime import date

import pandas as pd

from trading_engine.types import DataLoadError, PriceFrame


class VNStockLoader:
    """Loads historical OHLCV data from vnstock.

    Implements the DataLoader protocol.
    Tries primary source first, then fallback. Retries 2x on timeout.
    """

    MAX_RETRIES = 2

    def __init__(self, source: str = "KBS"):
        self.source = source
        self._fallback = "VCI" if source == "KBS" else "KBS"

    def load(self, symbol: str, start: date, end: date) -> PriceFrame:
        from vnstock import Quote

        sources_to_try = [self.source, self._fallback]

        for source in sources_to_try:
            last_error: Exception | None = None
            for attempt in range(self.MAX_RETRIES + 1):
                try:
                    q = Quote(symbol=symbol.upper(), source=source)
                    raw = q.history(
                        start=start.isoformat(),
                        end=end.isoformat(),
                        interval="1D",
                    )
                    if raw is not None and not raw.empty:
                        return self._normalize(raw, symbol)
                    break  # empty result, try next source
                except Exception as e:
                    last_error = e
                    if attempt < self.MAX_RETRIES:
                        continue
                    break  # exhausted retries for this source

        raise DataLoadError(
            f"No data for {symbol} from vnstock (tried: {sources_to_try}). "
            f"Last error: {last_error}"
        )

    @staticmethod
    def _normalize(raw: pd.DataFrame, symbol: str) -> PriceFrame:
        """Normalize vnstock output to standard PriceFrame format."""
        raw = raw.copy()
        raw["time"] = pd.to_datetime(raw["time"]).dt.normalize()
        raw = raw.set_index("time")
        raw.index.name = "date"

        rename_map = {
            "close": "close",
            "open": "open",
            "high": "high",
            "low": "low",
            "volume": "volume",
        }
        raw = raw.rename(columns=rename_map)

        keep = [c for c in ["open", "high", "low", "close", "volume"] if c in raw.columns]
        df = raw[keep].dropna(subset=["open", "high", "low", "close"])

        return PriceFrame(symbol=symbol.upper(), data=df, source="vnstock")
