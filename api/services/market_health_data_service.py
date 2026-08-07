"""Close-only stored-data access for Market Health calculations."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

import pandas as pd

from api.repositories.price_bar_repository import MarketHealthRepository, PriceBarQuery
from api.services.price_history_service import (
    DEFAULT_PRICE_BASIS,
    PriceHistoryNotFoundError,
    UnknownPriceUniverseError,
)


@dataclass(frozen=True)
class MarketHealthHistoryMetadata:
    fetched_at: datetime
    first_date: date
    last_date: date
    symbol_count: int
    row_count: int
    sources: tuple[str, ...]
    price_basis: str


@dataclass(frozen=True)
class MarketHealthHistory:
    universe: str
    closes: pd.DataFrame
    metadata: MarketHealthHistoryMetadata


class MarketHealthDataService:
    def __init__(self, repository: MarketHealthRepository):
        self._repository = repository

    def get_latest_date(self, universe: str) -> date:
        normalized, market = self._resolve_universe(universe)
        latest = self._repository.get_latest_date(
            normalized, DEFAULT_PRICE_BASIS[market]
        )
        if latest is None:
            raise PriceHistoryNotFoundError(
                f"{normalized} has no stored price history"
            )
        return latest

    def get_close_history(
        self,
        universe: str,
        *,
        start: date | None = None,
        end: date | None = None,
    ) -> MarketHealthHistory:
        normalized, market = self._resolve_universe(universe)
        if start and end and start > end:
            raise ValueError("Price-history start date must not be after end date")
        basis = DEFAULT_PRICE_BASIS[market]
        closes = self._repository.load_close_matrix(PriceBarQuery(
            universe=normalized,
            price_basis=basis,
            start=start,
            end=end,
        ))
        if closes.empty:
            raise PriceHistoryNotFoundError(
                f"{normalized} has no stored price history"
            )
        status = self._repository.get_status(
            normalized, basis, end or closes.index[-1].date()
        )
        if status is None:
            raise PriceHistoryNotFoundError(
                f"{normalized} has no stored price metadata"
            )
        return MarketHealthHistory(
            universe=normalized,
            closes=closes,
            metadata=MarketHealthHistoryMetadata(
                fetched_at=status.fetched_at,
                first_date=closes.index[0].date(),
                last_date=closes.index[-1].date(),
                symbol_count=int(closes.notna().any(axis=0).sum()),
                row_count=int(closes.notna().sum().sum()),
                sources=status.sources,
                price_basis=basis,
            ),
        )

    def _resolve_universe(self, universe: str) -> tuple[str, str]:
        normalized = universe.upper().strip()
        market = self._repository.get_universe_market(normalized)
        if market not in DEFAULT_PRICE_BASIS:
            raise UnknownPriceUniverseError(f"Unknown price universe: {universe}")
        return normalized, market
