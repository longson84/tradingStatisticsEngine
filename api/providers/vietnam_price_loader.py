"""DataLoader adapter backed by the configured Vietnam market provider."""
from __future__ import annotations

from datetime import date

from api.providers.vietnam_market import (
    ProviderDataError,
    ProviderUnavailableError,
    VietnamMarketProvider,
    create_vietnam_market_provider,
    normalize_ohlcv_result,
)
from trading_engine.types import DataLoadError, PriceFrame


class VietnamPriceLoader:
    """Load sponsored VN OHLCV while preserving the engine DataLoader contract."""

    def __init__(self, provider: VietnamMarketProvider | None = None) -> None:
        self._provider = provider

    def load(self, symbol: str, start: date, end: date) -> PriceFrame:
        provider = self._provider or create_vietnam_market_provider(
            require_sponsored=True
        )
        try:
            result = provider.ohlcv(symbol, start, end)
            normalized = normalize_ohlcv_result(result)
        except (ProviderDataError, ProviderUnavailableError, ValueError) as exc:
            raise DataLoadError(f"Failed to load {symbol} from vnstock_data: {exc}") from exc

        # DataLoader ranges are end-exclusive even though sponsored VCI ranges
        # are inclusive. Slice explicitly so strategies see one contract.
        normalized = normalized[
            (normalized["date"].dt.date >= start)
            & (normalized["date"].dt.date < end)
        ]
        if normalized.empty:
            raise DataLoadError(f"No sponsored VN data returned for {symbol}")
        source = str(normalized["provider_source"].iloc[-1])
        frame = normalized.set_index("date")[[
            "open", "high", "low", "close", "volume",
        ]]
        frame.index.name = "date"
        return PriceFrame(symbol=symbol.upper().strip(), data=frame, source=source)
