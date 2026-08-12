from __future__ import annotations

from datetime import time

import pytest

from api.instrument_data_routing import (
    InstrumentRoutingMetadata,
    ProviderSymbol,
    UnsupportedInstrumentRouteError,
    resolve_instrument_data_route,
)


def metadata(
    *,
    instrument_type: str = "common_stock",
    company_id: int | None = 1,
    venue_code: str | None = "NASDAQ",
    source: str = "test",
    symbol: str = "CANONICAL",
    provider_symbols: tuple[ProviderSymbol, ...] = (),
):
    return InstrumentRoutingMetadata(
        instrument_id=42,
        canonical_symbol=symbol,
        instrument_type=instrument_type,
        company_id=company_id,
        venue_code=venue_code,
        currency="USD" if venue_code != "HOSE" else "VND",
        catalog_source=source,
        provider_symbols=provider_symbols,
        timezone_name=(
            "America/New_York" if venue_code == "NASDAQ"
            else "Asia/Ho_Chi_Minh" if venue_code == "HOSE"
            else "UTC" if venue_code else None
        ),
        trading_calendar_code=(
            "US_EQUITIES" if venue_code == "NASDAQ"
            else "VN_EQUITIES" if venue_code == "HOSE"
            else "CRYPTO_24_7" if venue_code else None
        ),
        session_cutoff_time=(
            time(16, 15) if venue_code == "NASDAQ"
            else time(15, 15) if venue_code == "HOSE"
            else time(0, 0) if venue_code else None
        ),
    )


def test_equity_provider_and_symbol_are_derived_from_venue_and_namespace():
    us = resolve_instrument_data_route(metadata(
        symbol="BRK-B",
        provider_symbols=(ProviderSymbol("yfinance", "BRK-B"),),
    ))
    vn = resolve_instrument_data_route(metadata(
        venue_code="HOSE",
        symbol="FPT",
        provider_symbols=(ProviderSymbol("listing", "FPT"),),
    ))

    assert (us.price_adapter, us.provider_symbol, us.price_basis) == (
        "yfinance", "BRK-B", "adjusted"
    )
    assert (vn.price_adapter, vn.provider_symbol, vn.price_scale) == (
        "vnstock_data", "FPT", 1_000
    )


def test_spot_and_reference_rate_routes_keep_venue_and_source_distinct():
    spot = resolve_instrument_data_route(metadata(
        instrument_type="spot",
        company_id=None,
        venue_code="BINANCE_SPOT",
        symbol="BTCUSDT",
        provider_symbols=(ProviderSymbol("binance_spot", "BTCUSDT"),),
    ))
    rate = resolve_instrument_data_route(metadata(
        instrument_type="reference_rate",
        company_id=None,
        venue_code=None,
        source="yahoo_finance",
        symbol="BTC-USD",
        provider_symbols=(ProviderSymbol("yahoo_finance", "BTC-USD"),),
    ))

    assert spot.price_adapter == "binance_spot"
    assert spot.price_basis == "venue_unadjusted"
    assert rate.price_adapter == "yfinance"
    assert rate.full_history_start.isoformat() == "2014-09-17"


def test_missing_equity_venue_is_not_silently_routed_by_market_hint():
    with pytest.raises(UnsupportedInstrumentRouteError, match="venue none"):
        resolve_instrument_data_route(metadata(venue_code=None))


def test_company_link_does_not_make_an_unknown_instrument_type_an_equity():
    with pytest.raises(UnsupportedInstrumentRouteError, match="instrument type bond"):
        resolve_instrument_data_route(metadata(instrument_type="bond"))
