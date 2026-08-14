"""Resolve provider symbols to canonical equity venues before persistence."""
from __future__ import annotations

from dataclasses import replace

from api.equity_venues import canonical_equity_venue_code
from api.providers.nasdaq_symbol_directory import USListingVenueCatalog
from api.providers.universe import (
    UniverseProviderDataError,
    UniverseSnapshot,
    normalize_symbol,
)


def resolve_snapshot_venues(
    snapshot: UniverseSnapshot,
    *,
    us_catalog: USListingVenueCatalog | None = None,
) -> UniverseSnapshot:
    """Return a snapshot whose exchange values are canonical Venue codes."""
    directory = _directory_by_symbol(us_catalog) if us_catalog is not None else {}
    resolved = []
    for constituent in snapshot.constituents:
        venue_code = canonical_equity_venue_code(
            snapshot.listing_country_code,
            constituent.exchange,
        )
        if venue_code is None and snapshot.listing_country_code == "US":
            venue_code = directory.get(constituent.canonical_symbol)
        if venue_code is None:
            raise UniverseProviderDataError(
                f"{snapshot.code} has no canonical Venue for "
                f"{constituent.canonical_symbol}"
            )
        resolved.append(replace(constituent, exchange=venue_code))
    return replace(snapshot, constituents=tuple(resolved))


def needs_us_listing_catalog(snapshot: UniverseSnapshot) -> bool:
    return snapshot.listing_country_code == "US" and any(
        canonical_equity_venue_code(
            snapshot.listing_country_code,
            row.exchange,
        ) is None
        for row in snapshot.constituents
    )


def _directory_by_symbol(
    catalog: USListingVenueCatalog | None,
) -> dict[str, str]:
    if catalog is None:
        return {}
    values: dict[str, str] = {}
    conflicts: set[str] = set()
    for listing in catalog.listings:
        for raw_symbol in (*listing.primary_symbols, *listing.alternate_symbols):
            try:
                symbol = normalize_symbol(raw_symbol, "US")
            except UniverseProviderDataError:
                continue
            previous = values.get(symbol)
            if previous is not None and previous != listing.venue_code:
                conflicts.add(symbol)
            values[symbol] = listing.venue_code
    for symbol in conflicts:
        values.pop(symbol, None)
    return values
