"""Ensure one canonical company price series is current for analysis."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from threading import Lock

import pandas as pd

from api.instrument_data_routing import (
    InstrumentDataRoute,
    UnsupportedInstrumentRouteError,
    resolve_instrument_data_route,
)
from api.market_sessions import latest_completed_venue_session
from api.repositories.instrument_routing_repository import (
    InstrumentRoutingRepository,
)
from api.repositories.price_bar_repository import (
    PriceBarRecord,
    PriceBarRepository,
    PriceBarWriteRecord,
    PriceInstrumentRecord,
    InstrumentPriceBarQuery,
)
from trading_engine.types import DataLoadError, DataLoader, PriceFrame


FULL_HISTORY_START = date(2000, 1, 1)
REFRESH_OVERLAP_DAYS = 7
_lock_guard = Lock()
_symbol_locks: dict[int, Lock] = {}
_checked_sessions: dict[int, date] = {}


class UnknownCompanyError(ValueError):
    pass


class CompanyPriceUnavailableError(ValueError):
    pass


@dataclass(frozen=True)
class CompanyPriceData:
    prices: PriceFrame
    expected_last_session: date
    data_last_session: date
    refreshed: bool
    is_stale: bool
    refresh_warning: str | None
    price_source: str
    price_basis: str


class CompanyPriceService:
    def __init__(
        self,
        repository: PriceBarRepository,
        routing_repository: InstrumentRoutingRepository,
        loaders: dict[str, DataLoader],
    ):
        self._repository = repository
        self._routing_repository = routing_repository
        self._loaders = loaders

    def get_current_instrument_history(
        self,
        instrument_id: int,
        *,
        now: datetime | None = None,
    ) -> CompanyPriceData:
        instrument = self._repository.get_instrument(instrument_id)
        if instrument is None:
            raise UnknownCompanyError(f"Unknown equity instrument: {instrument_id}")
        return self._get_current_history(instrument, now=now)

    def _get_current_history(
        self,
        instrument: PriceInstrumentRecord,
        *,
        now: datetime | None,
    ) -> CompanyPriceData:
        route = self._route(instrument.instrument_id)
        if route.fundamental_adapter is None:
            raise UnknownCompanyError(
                f"Instrument {instrument.instrument_id} is not a supported equity"
            )
        normalized_ticker = instrument.ticker
        current = now or datetime.now(UTC)
        expected = latest_completed_venue_session(current, route.schedule)
        basis = route.price_basis
        key = instrument.instrument_id
        lock = _symbol_lock(key)
        refreshed = False
        warning: str | None = None
        with lock:
            coverage = self._repository.get_instrument_coverage(
                instrument.instrument_id, basis
            )
            already_checked = _checked_sessions.get(key) == expected
            if (coverage is None or coverage.last_date < expected) and not already_checked:
                start = (
                    coverage.last_date - timedelta(days=REFRESH_OVERLAP_DAYS)
                    if coverage else FULL_HISTORY_START
                )
                try:
                    fetched = self._loaders[route.price_adapter].load(
                        route.provider_symbol,
                        start,
                        expected + timedelta(days=1),
                    )
                    self._store_frame(
                        instrument, route, fetched, current
                    )
                    refreshed = True
                except (DataLoadError, ValueError, KeyError) as exc:
                    warning = f"Automatic refresh failed: {exc}"
                finally:
                    _checked_sessions[key] = expected
                coverage = self._repository.get_instrument_coverage(
                    instrument.instrument_id, basis
                )
            elif coverage is not None and coverage.last_date < expected:
                warning = "Automatic refresh was already attempted for this venue session"

        if coverage is None:
            raise CompanyPriceUnavailableError(
                warning or f"No stored price history for instrument {instrument.instrument_id} ({normalized_ticker})"
            )
        records = tuple(self._repository.iter_instrument_bars(InstrumentPriceBarQuery(
            instrument_id=instrument.instrument_id,
            price_basis=basis,
        )))
        if not records:
            raise CompanyPriceUnavailableError(
                f"No stored price history for instrument {instrument.instrument_id} ({normalized_ticker})"
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
            expected_last_session=expected,
            data_last_session=last_date,
            refreshed=refreshed,
            is_stale=last_date < expected,
            refresh_warning=warning,
            price_source=coverage.source,
            price_basis=basis,
        )

    def _store_frame(
        self,
        instrument: PriceInstrumentRecord,
        route: InstrumentDataRoute,
        prices: PriceFrame,
        fetched_at: datetime,
    ) -> None:
        source = prices.source
        records = (
            PriceBarWriteRecord(
                instrument_id=instrument.instrument_id,
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
                currency=route.currency,
                price_scale=route.price_scale,
                price_basis=route.price_basis,
                source=source,
                fetched_at=fetched_at,
            )
            for index, row in prices.data.iterrows()
        )
        self._repository.upsert_bars(records)

    def store_downloaded_histories(
        self,
        prices: dict[int, PriceFrame],
        *,
        fetched_at: datetime,
    ) -> int:
        if fetched_at.tzinfo is None:
            raise ValueError("fetched_at must be timezone-aware")
        targets: dict[int, PriceInstrumentRecord] = {}
        routes: dict[int, InstrumentDataRoute] = {}
        for instrument_id, frame in prices.items():
            target = self._repository.get_instrument(instrument_id)
            if target is None:
                raise ValueError(f"Unknown equity instrument: {instrument_id}")
            route = self._route(instrument_id)
            if route.fundamental_adapter is None:
                raise ValueError(f"Unsupported equity instrument: {instrument_id}")
            if frame.symbol.upper().strip() != route.provider_symbol:
                raise ValueError(
                    f"Price history for {frame.symbol} cannot update instrument "
                    f"{instrument_id} ({route.provider_symbol})"
                )
            targets[instrument_id] = target
            routes[instrument_id] = route
        records = (
            PriceBarWriteRecord(
                instrument_id=instrument_id,
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
                currency=route.currency,
                price_scale=route.price_scale,
                price_basis=route.price_basis,
                source=frame.source,
                fetched_at=fetched_at,
            )
            for instrument_id, frame in prices.items()
            for target in (targets[instrument_id],)
            for route in (routes[instrument_id],)
            for index, row in frame.data.iterrows()
        )
        return self._repository.upsert_bars(records)

    def _route(self, instrument_id: int) -> InstrumentDataRoute:
        metadata = self._routing_repository.get_instrument_route_metadata(
            instrument_id
        )
        if metadata is None:
            raise UnknownCompanyError(f"Unknown instrument: {instrument_id}")
        try:
            return resolve_instrument_data_route(metadata)
        except UnsupportedInstrumentRouteError as exc:
            raise UnknownCompanyError(str(exc)) from exc


def _symbol_lock(key: int) -> Lock:
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
