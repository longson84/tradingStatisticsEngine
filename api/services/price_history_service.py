"""Stored price-history use cases independent from SQLAlchemy and FastAPI."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

import pandas as pd

from api.repositories.price_bar_repository import (
    PriceBarQuery,
    PriceBarRecord,
    PriceBarRepository,
)
from trading_engine.types import PriceFrame


DEFAULT_PRICE_BASIS = {
    "US": "adjusted",
    "VN": "provider_unspecified",
}


class UnknownPriceUniverseError(ValueError):
    pass


class PriceHistoryNotFoundError(ValueError):
    pass


@dataclass(frozen=True)
class PriceHistoryMetadata:
    fetched_at: datetime
    first_date: date
    last_date: date
    symbol_count: int
    row_count: int
    sources: tuple[str, ...]
    price_basis: str
    currency: str
    price_scale: int


@dataclass(frozen=True)
class SymbolPriceHistory:
    universe: str
    prices: PriceFrame
    metadata: PriceHistoryMetadata


@dataclass(frozen=True)
class UniversePriceHistory:
    universe: str
    prices: dict[str, PriceFrame]
    metadata: PriceHistoryMetadata


class PriceHistoryService:
    def __init__(self, repository: PriceBarRepository):
        self._repository = repository

    def get_symbol_history(
        self,
        universe: str,
        ticker: str,
        *,
        start: date | None = None,
        end: date | None = None,
    ) -> SymbolPriceHistory:
        normalized_universe, market = self._resolve_universe(universe)
        normalized_ticker = ticker.upper().strip()
        if not normalized_ticker:
            raise PriceHistoryNotFoundError("A ticker is required")
        self._validate_range(start, end)
        records = tuple(self._repository.iter_bars(PriceBarQuery(
            universe=normalized_universe,
            ticker=normalized_ticker,
            price_basis=DEFAULT_PRICE_BASIS[market],
            start=start,
            end=end,
        )))
        if not records:
            raise PriceHistoryNotFoundError(
                f"{normalized_ticker} has no stored history in {normalized_universe}"
            )
        metadata = _metadata(records)
        return SymbolPriceHistory(
            universe=normalized_universe,
            prices=_price_frame(normalized_ticker, records),
            metadata=metadata,
        )

    def get_latest_date(self, universe: str) -> date:
        normalized_universe, market = self._resolve_universe(universe)
        latest = self._repository.get_latest_date(
            normalized_universe, DEFAULT_PRICE_BASIS[market]
        )
        if latest is None:
            raise PriceHistoryNotFoundError(
                f"{normalized_universe} has no stored price history"
            )
        return latest

    def get_universe_history(
        self,
        universe: str,
        *,
        start: date | None = None,
        end: date | None = None,
    ) -> UniversePriceHistory:
        normalized_universe, market = self._resolve_universe(universe)
        self._validate_range(start, end)
        prices: dict[str, PriceFrame] = {}
        current_ticker: str | None = None
        current_records: list[PriceBarRecord] = []
        fetched_at: datetime | None = None
        first_date: date | None = None
        last_date: date | None = None
        row_count = 0
        sources: set[str] = set()
        bases: set[str] = set()
        currencies: set[str] = set()
        scales: set[int] = set()
        for record in self._repository.iter_bars(PriceBarQuery(
            universe=normalized_universe,
            price_basis=DEFAULT_PRICE_BASIS[market],
            start=start,
            end=end,
        )):
            if current_ticker is not None and record.ticker != current_ticker:
                prices[current_ticker] = _price_frame(
                    current_ticker, current_records
                )
                current_records = []
            current_ticker = record.ticker
            current_records.append(record)
            fetched_at = (
                record.fetched_at
                if fetched_at is None
                else max(fetched_at, record.fetched_at)
            )
            first_date = (
                record.trading_date
                if first_date is None
                else min(first_date, record.trading_date)
            )
            last_date = (
                record.trading_date
                if last_date is None
                else max(last_date, record.trading_date)
            )
            row_count += 1
            sources.add(record.source)
            bases.add(record.price_basis)
            currencies.add(record.currency)
            scales.add(record.price_scale)
        if current_ticker is not None:
            prices[current_ticker] = _price_frame(current_ticker, current_records)
        if not prices or fetched_at is None or first_date is None or last_date is None:
            raise PriceHistoryNotFoundError(
                f"{normalized_universe} has no stored price history"
            )
        if len(bases) != 1 or len(currencies) != 1 or len(scales) != 1:
            raise ValueError("Stored price history contains inconsistent units or basis")
        return UniversePriceHistory(
            universe=normalized_universe,
            prices=prices,
            metadata=PriceHistoryMetadata(
                fetched_at=fetched_at,
                first_date=first_date,
                last_date=last_date,
                symbol_count=len(prices),
                row_count=row_count,
                sources=tuple(sorted(sources)),
                price_basis=next(iter(bases)),
                currency=next(iter(currencies)),
                price_scale=next(iter(scales)),
            ),
        )

    def _resolve_universe(self, universe: str) -> tuple[str, str]:
        normalized = universe.upper().strip()
        market = self._repository.get_universe_market(normalized)
        if market not in DEFAULT_PRICE_BASIS:
            raise UnknownPriceUniverseError(f"Unknown price universe: {universe}")
        return normalized, market

    @staticmethod
    def _validate_range(start: date | None, end: date | None) -> None:
        if start and end and start > end:
            raise ValueError("Price-history start date must not be after end date")


def _price_frame(ticker: str, records: list[PriceBarRecord] | tuple[PriceBarRecord, ...]) -> PriceFrame:
    index = pd.DatetimeIndex(
        [record.trading_date for record in records], name="date"
    )
    frame = pd.DataFrame(
        {
            "open": [record.open for record in records],
            "high": [record.high for record in records],
            "low": [record.low for record in records],
            "close": [record.close for record in records],
            "volume": [record.volume for record in records],
        },
        index=index,
        dtype=float,
    )
    sources = sorted({record.source for record in records})
    source = sources[0] if len(sources) == 1 else f"database:{','.join(sources)}"
    return PriceFrame(symbol=ticker, data=frame, source=source)


def _metadata(
    records: list[PriceBarRecord] | tuple[PriceBarRecord, ...],
) -> PriceHistoryMetadata:
    bases = {record.price_basis for record in records}
    currencies = {record.currency for record in records}
    scales = {record.price_scale for record in records}
    if len(bases) != 1 or len(currencies) != 1 or len(scales) != 1:
        raise ValueError("Stored price history contains inconsistent units or basis")
    return PriceHistoryMetadata(
        fetched_at=max(record.fetched_at for record in records),
        first_date=min(record.trading_date for record in records),
        last_date=max(record.trading_date for record in records),
        symbol_count=len({record.ticker for record in records}),
        row_count=len(records),
        sources=tuple(sorted({record.source for record in records})),
        price_basis=next(iter(bases)),
        currency=next(iter(currencies)),
        price_scale=next(iter(scales)),
    )
