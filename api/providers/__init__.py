"""External market-data provider adapters owned by the application layer."""

from api.providers.vietnam_fundamentals import (
    VietnamFundamentalMetadata,
    VietnamFundamentalResult,
    VnstockDataFundamentalProvider,
    fundamental_methodology,
    fundamental_source_label,
)

from api.providers.vietnam_market import (
    CommunityVnstockProvider,
    ProviderDataError,
    ProviderUnavailableError,
    UnsupportedProviderMethodError,
    VietnamMarketProvider,
    VietnamProviderMetadata,
    VietnamProviderResult,
    VnstockDataProvider,
    create_vietnam_market_provider,
    normalize_ohlcv_result,
    provider_runtime_label,
    provider_source_label,
)
from api.providers.vietnam_price_loader import VietnamPriceLoader

__all__ = [
    "CommunityVnstockProvider",
    "ProviderDataError",
    "ProviderUnavailableError",
    "UnsupportedProviderMethodError",
    "VietnamMarketProvider",
    "VietnamProviderMetadata",
    "VietnamProviderResult",
    "VnstockDataProvider",
    "create_vietnam_market_provider",
    "normalize_ohlcv_result",
    "provider_runtime_label",
    "provider_source_label",
    "VietnamPriceLoader",
    "VietnamFundamentalMetadata",
    "VietnamFundamentalResult",
    "VnstockDataFundamentalProvider",
    "fundamental_methodology",
    "fundamental_source_label",
]
