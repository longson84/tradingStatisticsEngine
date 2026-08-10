"""Default provider composition for all system-managed company universes."""
from __future__ import annotations

from api.providers.universe import UniverseProviderRegistry
from api.providers.us_universes import (
    IsharesRussell2000UniverseProvider,
    Nasdaq100UniverseProvider,
    WikipediaUSIndexProvider,
)
from api.providers.vietnam_universes import VnstockUniverseProvider


def create_universe_provider_registry() -> UniverseProviderRegistry:
    return UniverseProviderRegistry((
        Nasdaq100UniverseProvider(),
        IsharesRussell2000UniverseProvider(),
        WikipediaUSIndexProvider(),
        VnstockUniverseProvider(),
    ))
