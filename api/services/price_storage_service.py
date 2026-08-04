"""Price-storage status and maintenance use cases."""
from __future__ import annotations

from dataclasses import dataclass

from api.repositories.price_bar_repository import (
    PriceBarMaintenanceRepository,
    PriceBarStatusRecord,
)
from api.services.price_history_service import (
    DEFAULT_PRICE_BASIS,
    UnknownPriceUniverseError,
)


@dataclass(frozen=True)
class PriceMarketClearResult:
    market: str
    affected_universes: tuple[str, ...]
    deleted_rows: int


class PriceStorageService:
    def __init__(self, repository: PriceBarMaintenanceRepository):
        self._repository = repository

    def get_status(self, universe: str) -> PriceBarStatusRecord | None:
        normalized, market = self._resolve_universe(universe)
        return self._repository.get_status(
            normalized, DEFAULT_PRICE_BASIS[market]
        )

    def clear_market_for_universe(self, universe: str) -> PriceMarketClearResult:
        _, market = self._resolve_universe(universe)
        affected = self._repository.list_market_universes(market)
        deleted_rows = self._repository.delete_market_bars(market)
        return PriceMarketClearResult(
            market=market,
            affected_universes=affected,
            deleted_rows=deleted_rows,
        )

    def _resolve_universe(self, universe: str) -> tuple[str, str]:
        normalized = universe.upper().strip()
        market = self._repository.get_universe_market(normalized)
        if market not in DEFAULT_PRICE_BASIS:
            raise UnknownPriceUniverseError(f"Unknown price universe: {universe}")
        return normalized, market
