"""Ensure one canonical company price series is current for analysis."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from threading import Lock

import pandas as pd

from api.market_sessions import latest_completed_session
from api.repositories.price_bar_repository import (
    PriceBarRecord,
    PriceBarRepository,
    PriceBarWriteRecord,
    SymbolPriceBarQuery,
    SymbolSetPriceBarQuery,
)
from api.services.price_history_service import DEFAULT_PRICE_BASIS
from trading_engine.types import DataLoadError, DataLoader, PriceFrame


FULL_HISTORY_START = date(2000, 1, 1)
REFRESH_OVERLAP_DAYS = 7
_lock_guard = Lock()
_symbol_locks: dict[tuple[str, str], Lock] = {}
_checked_sessions: dict[tuple[str, str], date] = {}


class UnknownCompanyError(ValueError):
    pass


class CompanyPriceUnavailableError(ValueError):
    pass


@dataclass(frozen=True)
class CompanyPriceData:
    prices: PriceFrame
    market: str
    expected_last_session: date
    data_last_session: date
    refreshed: bool
    is_stale: bool
    refresh_warning: str | None
    price_source: str
    price_basis: str


@dataclass(frozen=True)
class StoredCompanyPriceData:
    prices: dict[str, PriceFrame]
    expected_last_session: date
    missing_tickers: tuple[str, ...]
    stale_tickers: tuple[str, ...]
    price_basis: str


class CompanyPriceService:
    def __init__(
        self,
        repository: PriceBarRepository,
        loaders: dict[str, DataLoader],
    ):
        self._repository = repository
        self._loaders = loaders

    def get_current_history(
        self,
        market: str,
        ticker: str,
        *,
        now: datetime | None = None,
    ) -> CompanyPriceData:
        normalized_market = market.upper().strip()
        normalized_ticker = ticker.upper().strip()
        if normalized_market not in DEFAULT_PRICE_BASIS or not normalized_ticker:
            raise UnknownCompanyError("A valid market and ticker are required")
        if not self._repository.instrument_exists(
            normalized_market, normalized_ticker
        ):
            raise UnknownCompanyError(
                f"Unknown company: {normalized_market}-{normalized_ticker}"
            )
        current = now or datetime.now(UTC)
        expected = latest_completed_session(current, normalized_market)
        basis = DEFAULT_PRICE_BASIS[normalized_market]
        key = (normalized_market, normalized_ticker)
        lock = _symbol_lock(key)
        refreshed = False
        warning: str | None = None
        with lock:
            coverage = self._repository.get_symbol_coverage(
                normalized_market, normalized_ticker, basis
            )
            already_checked = _checked_sessions.get(key) == expected
            if (coverage is None or coverage.last_date < expected) and not already_checked:
                start = (
                    coverage.last_date - timedelta(days=REFRESH_OVERLAP_DAYS)
                    if coverage else FULL_HISTORY_START
                )
                try:
                    fetched = self._loaders[normalized_market].load(
                        normalized_ticker,
                        start,
                        expected + timedelta(days=1),
                    )
                    self._store_frame(
                        normalized_market, normalized_ticker, basis, fetched, current
                    )
                    refreshed = True
                except (DataLoadError, ValueError, KeyError) as exc:
                    warning = f"Automatic refresh failed: {exc}"
                finally:
                    _checked_sessions[key] = expected
                coverage = self._repository.get_symbol_coverage(
                    normalized_market, normalized_ticker, basis
                )
            elif coverage is not None and coverage.last_date < expected:
                warning = "Automatic refresh was already attempted for this market session"

        if coverage is None:
            raise CompanyPriceUnavailableError(
                warning or f"No stored price history for {normalized_market}-{normalized_ticker}"
            )
        records = tuple(self._repository.iter_symbol_bars(SymbolPriceBarQuery(
            market=normalized_market,
            ticker=normalized_ticker,
            price_basis=basis,
        )))
        if not records:
            raise CompanyPriceUnavailableError(
                f"No stored price history for {normalized_market}-{normalized_ticker}"
            )
        frame = pd.DataFrame(
            {
                "open": [row.open for row in records],
                "high": [row.high for row in records],
                "low": [row.low for row in records],
                "close": [row.close for row in records],
                "volume": [row.volume for row in records],
            },
            index=pd.DatetimeIndex([row.trading_date for row in records], name="date"),
        )
        last_date = records[-1].trading_date
        return CompanyPriceData(
            prices=PriceFrame(
                symbol=normalized_ticker,
                data=frame,
                source=coverage.source,
            ),
            market=normalized_market,
            expected_last_session=expected,
            data_last_session=last_date,
            refreshed=refreshed,
            is_stale=last_date < expected,
            refresh_warning=warning,
            price_source=coverage.source,
            price_basis=basis,
        )

    def get_stored_histories(
        self,
        market: str,
        tickers: list[str] | tuple[str, ...],
        *,
        now: datetime | None = None,
    ) -> StoredCompanyPriceData:
        normalized_market = market.upper().strip()
        if normalized_market not in DEFAULT_PRICE_BASIS:
            raise ValueError("Market must be US or VN")
        normalized_tickers = tuple(dict.fromkeys(
            ticker.upper().strip() for ticker in tickers if ticker.strip()
        ))
        basis = DEFAULT_PRICE_BASIS[normalized_market]
        expected = latest_completed_session(now or datetime.now(UTC), normalized_market)
        coverages = {
            row.ticker: row
            for row in self._repository.list_symbol_coverages(
                normalized_market, normalized_tickers, basis
            )
        }
        grouped: dict[str, list[PriceBarRecord]] = {}
        for row in self._repository.iter_symbol_set_bars(SymbolSetPriceBarQuery(
            market=normalized_market,
            tickers=normalized_tickers,
            price_basis=basis,
        )):
            grouped.setdefault(row.ticker, []).append(row)
        prices = {
            ticker: _price_frame(ticker, rows)
            for ticker, rows in grouped.items()
            if rows
        }
        return StoredCompanyPriceData(
            prices=prices,
            expected_last_session=expected,
            missing_tickers=tuple(
                ticker for ticker in normalized_tickers if ticker not in prices
            ),
            stale_tickers=tuple(
                ticker
                for ticker in normalized_tickers
                if ticker in coverages and coverages[ticker].last_date < expected
            ),
            price_basis=basis,
        )

    def _store_frame(
        self,
        market: str,
        ticker: str,
        basis: str,
        prices: PriceFrame,
        fetched_at: datetime,
    ) -> None:
        currency = "VND" if market == "VN" else "USD"
        scale = 1_000 if market == "VN" else 1
        source = prices.source
        records = (
            PriceBarWriteRecord(
                market=market,
                ticker=ticker,
                trading_date=pd.Timestamp(index).date(),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=(
                    float(row["volume"])
                    if "volume" in row and not pd.isna(row["volume"])
                    else None
                ),
                currency=currency,
                price_scale=scale,
                price_basis=basis,
                source=source,
                fetched_at=fetched_at,
            )
            for index, row in prices.data.iterrows()
        )
        self._repository.upsert_bars(records)

    def store_downloaded_histories(
        self,
        market: str,
        prices: dict[str, PriceFrame],
        *,
        fetched_at: datetime,
    ) -> int:
        normalized_market = market.upper().strip()
        if normalized_market not in DEFAULT_PRICE_BASIS:
            raise ValueError("Market must be US or VN")
        if fetched_at.tzinfo is None:
            raise ValueError("fetched_at must be timezone-aware")
        basis = DEFAULT_PRICE_BASIS[normalized_market]
        currency = "VND" if normalized_market == "VN" else "USD"
        scale = 1_000 if normalized_market == "VN" else 1
        records = (
            PriceBarWriteRecord(
                market=normalized_market,
                ticker=ticker.upper().strip(),
                trading_date=pd.Timestamp(index).date(),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=(
                    float(row["volume"])
                    if "volume" in row and not pd.isna(row["volume"])
                    else None
                ),
                currency=currency,
                price_scale=scale,
                price_basis=basis,
                source=frame.source,
                fetched_at=fetched_at,
            )
            for ticker, frame in prices.items()
            for index, row in frame.data.iterrows()
        )
        return self._repository.upsert_bars(records)


def _symbol_lock(key: tuple[str, str]) -> Lock:
    with _lock_guard:
        return _symbol_locks.setdefault(key, Lock())


def _price_frame(ticker: str, records: list[PriceBarRecord]) -> PriceFrame:
    sources = sorted({row.source for row in records})
    return PriceFrame(
        symbol=ticker,
        data=pd.DataFrame(
            {
                "open": [row.open for row in records],
                "high": [row.high for row in records],
                "low": [row.low for row in records],
                "close": [row.close for row in records],
                "volume": [row.volume for row in records],
            },
            index=pd.DatetimeIndex(
                [row.trading_date for row in records], name="date"
            ),
        ),
        source=(sources[0] if len(sources) == 1 else f"database:{','.join(sources)}"),
    )
