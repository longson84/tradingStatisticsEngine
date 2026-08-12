"""Canonical provider routing derived from instrument and source metadata."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time
from typing import Literal

from api.repositories.instrument_analysis_repository import (
    DEFAULT_CANONICAL_PRICE_BASIS,
    SPOT_PRICE_BASIS,
    US_EQUITY_PRICE_BASIS,
)
from api.venue_calendars import (
    CONTINUOUS_DAILY_CALENDAR,
    VenueCalendarMetadata,
)


PriceAdapter = Literal["yfinance", "vnstock_data", "binance_spot"]
FundamentalAdapter = Literal["yfinance", "vnstock_data"]

US_EQUITY_VENUES = frozenset({
    "NASDAQ", "NYSE", "NYSE_AMERICAN", "NYSE_ARCA", "CBOE_BZX", "IEX",
})
VN_EQUITY_VENUES = frozenset({"HOSE", "HNX", "UPCOM"})


@dataclass(frozen=True)
class ProviderSymbol:
    namespace: str
    symbol: str


@dataclass(frozen=True)
class InstrumentRoutingMetadata:
    instrument_id: int
    canonical_symbol: str
    instrument_type: str
    company_id: int | None
    venue_code: str | None
    currency: str
    catalog_source: str
    provider_symbols: tuple[ProviderSymbol, ...] = ()
    timezone_name: str | None = None
    trading_calendar_code: str | None = None
    session_cutoff_time: time | None = None


@dataclass(frozen=True)
class InstrumentDataRoute:
    instrument_id: int
    price_adapter: PriceAdapter
    provider_symbol: str
    price_basis: str
    currency: str
    price_scale: int
    schedule: VenueCalendarMetadata
    full_history_start: date
    fundamental_adapter: FundamentalAdapter | None = None

    @property
    def coordination_key(self) -> str:
        return self.price_adapter


class UnsupportedInstrumentRouteError(ValueError):
    pass


def resolve_instrument_data_route(
    instrument: InstrumentRoutingMetadata,
) -> InstrumentDataRoute:
    """Resolve one deterministic adapter without consulting legacy market."""
    venue_code = instrument.venue_code.upper() if instrument.venue_code else None
    if instrument.instrument_type == "spot":
        if venue_code != "BINANCE_SPOT":
            raise UnsupportedInstrumentRouteError(
                f"No spot price adapter for venue {venue_code or 'none'}"
            )
        return InstrumentDataRoute(
            instrument_id=instrument.instrument_id,
            price_adapter="binance_spot",
            provider_symbol=_symbol(instrument, "binance_spot"),
            price_basis=SPOT_PRICE_BASIS,
            currency=instrument.currency,
            price_scale=1,
            schedule=instrument_observation_schedule(instrument),
            full_history_start=date(2017, 8, 17),
        )

    if instrument.instrument_type == "reference_rate":
        if instrument.venue_code is not None:
            raise UnsupportedInstrumentRouteError(
                "Reference-rate instruments must remain venue-less"
            )
        if instrument.catalog_source != "yahoo_finance":
            raise UnsupportedInstrumentRouteError(
                f"No reference-rate adapter for source {instrument.catalog_source}"
            )
        starts = {
            "BTC-USD": date(2014, 9, 17),
            "ETH-USD": date(2015, 8, 7),
        }
        provider_symbol = _symbol(instrument, "yahoo_finance")
        try:
            full_start = starts[provider_symbol]
        except KeyError as exc:
            raise UnsupportedInstrumentRouteError(
                f"No history boundary registered for {provider_symbol}"
            ) from exc
        return InstrumentDataRoute(
            instrument_id=instrument.instrument_id,
            price_adapter="yfinance",
            provider_symbol=provider_symbol,
            price_basis=DEFAULT_CANONICAL_PRICE_BASIS,
            currency=instrument.currency,
            price_scale=1,
            schedule=instrument_observation_schedule(instrument),
            full_history_start=full_start,
        )

    if instrument.instrument_type != "common_stock":
        raise UnsupportedInstrumentRouteError(
            f"No price adapter for instrument type {instrument.instrument_type}"
        )
    if instrument.company_id is None:
        raise UnsupportedInstrumentRouteError(
            f"Instrument {instrument.instrument_id} has no supported asset identity"
        )
    if venue_code in US_EQUITY_VENUES:
        return InstrumentDataRoute(
            instrument_id=instrument.instrument_id,
            price_adapter="yfinance",
            provider_symbol=_symbol(instrument, "yfinance", "canonical"),
            price_basis=US_EQUITY_PRICE_BASIS,
            currency=instrument.currency,
            price_scale=1,
            schedule=instrument_observation_schedule(instrument),
            full_history_start=date(1900, 1, 1),
            fundamental_adapter="yfinance",
        )
    if venue_code in VN_EQUITY_VENUES:
        return InstrumentDataRoute(
            instrument_id=instrument.instrument_id,
            price_adapter="vnstock_data",
            provider_symbol=_symbol(instrument, "listing", "canonical"),
            price_basis=DEFAULT_CANONICAL_PRICE_BASIS,
            currency=instrument.currency,
            price_scale=1_000,
            schedule=instrument_observation_schedule(instrument),
            full_history_start=date(2000, 1, 1),
            fundamental_adapter="vnstock_data",
        )
    raise UnsupportedInstrumentRouteError(
        f"No equity adapter for venue {venue_code or 'none'}"
    )


def _symbol(
    instrument: InstrumentRoutingMetadata,
    *namespaces: str,
) -> str:
    symbols = {
        row.namespace: row.symbol
        for row in instrument.provider_symbols
        if row.symbol.strip()
    }
    for namespace in namespaces:
        if symbol := symbols.get(namespace):
            return symbol.upper().strip()
    return instrument.canonical_symbol.upper().strip()


def instrument_observation_schedule(
    instrument: InstrumentRoutingMetadata,
) -> VenueCalendarMetadata:
    if instrument.venue_code is None:
        return VenueCalendarMetadata(
            timezone_name="UTC",
            trading_calendar_code=CONTINUOUS_DAILY_CALENDAR,
            session_cutoff_time=time(0, 0),
        )
    if not all((
        instrument.timezone_name,
        instrument.trading_calendar_code,
        instrument.session_cutoff_time is not None,
    )):
        raise UnsupportedInstrumentRouteError(
            f"Instrument {instrument.instrument_id} has incomplete venue calendar metadata"
        )
    return VenueCalendarMetadata(
        timezone_name=str(instrument.timezone_name),
        trading_calendar_code=str(instrument.trading_calendar_code),
        session_cutoff_time=instrument.session_cutoff_time,
    )
