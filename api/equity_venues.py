"""Canonical equity-venue registry and source-label normalization."""
from __future__ import annotations

from dataclasses import dataclass


EQUITY_VENUE_SOURCE = "system:equity-venue-registry"


@dataclass(frozen=True)
class EquityVenueDefinition:
    code: str
    name: str
    country_code: str
    venue_type: str = "exchange"


EQUITY_VENUES = (
    EquityVenueDefinition("NASDAQ", "Nasdaq Stock Market", "US"),
    EquityVenueDefinition("NYSE", "New York Stock Exchange", "US"),
    EquityVenueDefinition("NYSE_AMERICAN", "NYSE American", "US"),
    EquityVenueDefinition("NYSE_ARCA", "NYSE Arca", "US"),
    EquityVenueDefinition("CBOE_BZX", "Cboe BZX Exchange", "US"),
    EquityVenueDefinition("IEX", "Investors Exchange", "US"),
    EquityVenueDefinition("HOSE", "Ho Chi Minh Stock Exchange", "VN"),
    EquityVenueDefinition("HNX", "Hanoi Stock Exchange", "VN"),
    EquityVenueDefinition(
        "UPCOM",
        "Unlisted Public Company Market",
        "VN",
        venue_type="market",
    ),
)

EQUITY_VENUES_BY_CODE = {row.code: row for row in EQUITY_VENUES}

_EXCHANGE_ALIASES = {
    ("US", "NASDAQ"): "NASDAQ",
    ("US", "NASDAQ STOCK MARKET"): "NASDAQ",
    ("US", "NYSE"): "NYSE",
    ("US", "NEW YORK STOCK EXCHANGE"): "NYSE",
    ("US", "NYSE AMERICAN"): "NYSE_AMERICAN",
    ("US", "NYSE MKT"): "NYSE_AMERICAN",
    ("US", "AMEX"): "NYSE_AMERICAN",
    ("US", "NYSE ARCA"): "NYSE_ARCA",
    ("US", "ARCA"): "NYSE_ARCA",
    ("US", "BATS"): "CBOE_BZX",
    ("US", "BATS GLOBAL MARKETS"): "CBOE_BZX",
    ("US", "CBOE BZX"): "CBOE_BZX",
    ("US", "CBOE BZX EXCHANGE"): "CBOE_BZX",
    ("US", "IEX"): "IEX",
    ("US", "IEXG"): "IEX",
    ("US", "INVESTORS EXCHANGE"): "IEX",
    ("VN", "HOSE"): "HOSE",
    ("VN", "HSX"): "HOSE",
    ("VN", "HO CHI MINH STOCK EXCHANGE"): "HOSE",
    ("VN", "HNX"): "HNX",
    ("VN", "HANOI STOCK EXCHANGE"): "HNX",
    ("VN", "UPCOM"): "UPCOM",
    ("VN", "UPCOM MARKET"): "UPCOM",
}


def canonical_equity_venue_code(
    country_code: str,
    exchange: str | None,
) -> str | None:
    """Resolve a trusted exchange label to one canonical venue code."""
    if not exchange:
        return None
    country = country_code.upper().strip()
    label = " ".join(exchange.upper().replace("_", " ").split())
    return _EXCHANGE_ALIASES.get((country, label))

