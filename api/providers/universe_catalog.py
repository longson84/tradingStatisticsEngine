"""Default provider composition for system-managed equity Universes."""
from __future__ import annotations

from api.providers.universe import UniverseProviderRegistry
from api.providers.us_universes import (
    IsharesRussellUniverseProvider,
    Nasdaq100UniverseProvider,
    WikipediaUSIndexProvider,
)
from api.providers.vietnam_universes import VnstockUniverseProvider


def create_universe_provider_registry() -> UniverseProviderRegistry:
    return UniverseProviderRegistry((
        Nasdaq100UniverseProvider(),
        IsharesRussellUniverseProvider(),
        WikipediaUSIndexProvider(),
        VnstockUniverseProvider(),
    ))
