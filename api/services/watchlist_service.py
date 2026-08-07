"""Watchlist use cases independent from FastAPI and SQLAlchemy."""
from __future__ import annotations

from api.repositories.watchlist_repository import (
    WatchlistRecord,
    WatchlistRepository,
    WatchlistSummaryRecord,
)


class UnknownWatchlistError(ValueError):
    pass


class DuplicateWatchlistError(ValueError):
    pass


class InvalidWatchlistCompanyError(ValueError):
    pass


class WatchlistService:
    def __init__(self, repository: WatchlistRepository):
        self._repository = repository

    def list_watchlists(
        self, market: str | None = None
    ) -> tuple[WatchlistSummaryRecord, ...]:
        normalized_market = _market(market) if market is not None else None
        return self._repository.list_watchlists(normalized_market)

    def get_watchlist(self, watchlist_id: int) -> WatchlistRecord:
        watchlist = self._repository.get_watchlist(watchlist_id)
        if watchlist is None:
            raise UnknownWatchlistError(f"Unknown watchlist: {watchlist_id}")
        return watchlist

    def create_watchlist(
        self,
        *,
        name: str,
        market: str,
        description: str = "",
        tickers: list[str] | tuple[str, ...] = (),
    ) -> WatchlistRecord:
        normalized_market = _market(market)
        normalized_name, name_key = _name(name)
        normalized_tickers = _tickers(tickers)
        if self._repository.name_exists(normalized_market, name_key):
            raise DuplicateWatchlistError(
                f"A {normalized_market} watchlist named {normalized_name!r} already exists"
            )
        instrument_ids = self._resolve_members(
            normalized_market, normalized_tickers
        )
        watchlist_id = self._repository.create_watchlist(
            name=normalized_name,
            name_key=name_key,
            market=normalized_market,
            description=description.strip(),
        )
        self._repository.replace_members(
            watchlist_id, normalized_market, instrument_ids
        )
        return self.get_watchlist(watchlist_id)

    def update_watchlist(
        self,
        watchlist_id: int,
        *,
        name: str,
        description: str = "",
        tickers: list[str] | tuple[str, ...] = (),
    ) -> WatchlistRecord:
        existing = self.get_watchlist(watchlist_id)
        normalized_name, name_key = _name(name)
        if self._repository.name_exists(
            existing.market, name_key, exclude_id=watchlist_id
        ):
            raise DuplicateWatchlistError(
                f"A {existing.market} watchlist named {normalized_name!r} already exists"
            )
        instrument_ids = self._resolve_members(
            existing.market, _tickers(tickers)
        )
        if not self._repository.update_watchlist(
            watchlist_id,
            name=normalized_name,
            name_key=name_key,
            description=description.strip(),
        ):
            raise UnknownWatchlistError(f"Unknown watchlist: {watchlist_id}")
        self._repository.replace_members(watchlist_id, existing.market, instrument_ids)
        return self.get_watchlist(watchlist_id)

    def delete_watchlist(self, watchlist_id: int) -> None:
        if not self._repository.delete_watchlist(watchlist_id):
            raise UnknownWatchlistError(f"Unknown watchlist: {watchlist_id}")

    def _resolve_members(
        self, market: str, tickers: tuple[str, ...]
    ) -> tuple[int, ...]:
        resolved = self._repository.resolve_instrument_ids(market, tickers)
        missing = tuple(ticker for ticker in tickers if ticker not in resolved)
        if missing:
            raise InvalidWatchlistCompanyError(
                f"These tickers are not active {market} companies: {', '.join(missing)}"
            )
        return tuple(resolved[ticker] for ticker in tickers)


def _market(value: str) -> str:
    market = value.upper().strip()
    if market not in {"US", "VN"}:
        raise ValueError("Watchlist market must be US or VN")
    return market


def _name(value: str) -> tuple[str, str]:
    name = " ".join(value.split())
    if not name:
        raise ValueError("Watchlist name is required")
    return name, name.casefold()


def _tickers(values: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        ticker = value.upper().strip()
        if ticker and ticker not in seen:
            seen.add(ticker)
            result.append(ticker)
    return tuple(result)
