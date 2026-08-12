"""Reconcile current US equity listing venues from an official directory."""
from __future__ import annotations

from dataclasses import dataclass
import re

from api.providers.nasdaq_symbol_directory import USListingVenueCatalog
from api.repositories.equity_venue_repository import (
    EquityVenueAssignment,
    EquityVenueRepository,
)


class EquityVenueSyncError(ValueError):
    pass


@dataclass(frozen=True)
class EquityVenueSyncResult:
    received_listings: int
    instrument_count: int
    matched_instruments: int
    updated_instruments: int
    unchanged_instruments: int
    unresolved_symbols: tuple[str, ...]
    ambiguous_symbols: tuple[str, ...]


class EquityVenueService:
    def __init__(self, repository: EquityVenueRepository) -> None:
        self._repository = repository

    def sync_us_listing_venues(
        self,
        catalog: USListingVenueCatalog,
    ) -> EquityVenueSyncResult:
        if catalog.fetched_at.tzinfo is None:
            raise EquityVenueSyncError("Venue catalog fetched_at must be timezone-aware")
        if not catalog.listings:
            raise EquityVenueSyncError("Venue catalog must not be empty")

        primary_venues_by_symbol: dict[str, set[str]] = {}
        alternate_venues_by_symbol: dict[str, set[str]] = {}
        loose_venues_by_symbol: dict[str, set[str]] = {}
        for listing in catalog.listings:
            for symbol in listing.primary_symbols:
                primary_venues_by_symbol.setdefault(
                    _exact_symbol_key(symbol), set()
                ).add(listing.venue_code)
            for symbol in listing.alternate_symbols:
                alternate_venues_by_symbol.setdefault(
                    _exact_symbol_key(symbol), set()
                ).add(listing.venue_code)
            for symbol in (*listing.primary_symbols, *listing.alternate_symbols):
                loose_venues_by_symbol.setdefault(
                    _loose_symbol_key(symbol), set()
                ).add(listing.venue_code)

        self._repository.ensure_venue_registry()
        instruments = self._repository.list_us_equity_instruments()
        assignments = []
        matched = 0
        unchanged = 0
        unresolved = []
        ambiguous = []
        for instrument in instruments:
            symbols = (instrument.symbol, *instrument.symbol_aliases)
            candidates = set()
            for symbol in symbols:
                candidates.update(
                    primary_venues_by_symbol.get(_exact_symbol_key(symbol), ())
                )
            if not candidates:
                for symbol in symbols:
                    candidates.update(
                        alternate_venues_by_symbol.get(
                            _exact_symbol_key(symbol), ()
                        )
                    )
            if not candidates:
                # Only relax punctuation when neither a primary nor alternate
                # official symbol provided an exact match. This supports class
                # symbols without letting a CQS alias override an exact listing.
                for symbol in symbols:
                    candidates.update(
                        loose_venues_by_symbol.get(_loose_symbol_key(symbol), ())
                    )
            if not candidates:
                unresolved.append(instrument.symbol)
                continue
            if len(candidates) != 1:
                ambiguous.append(instrument.symbol)
                continue
            matched += 1
            venue_code = next(iter(candidates))
            if instrument.venue_code == venue_code:
                unchanged += 1
                continue
            assignments.append(EquityVenueAssignment(
                instrument_id=instrument.instrument_id,
                venue_code=venue_code,
            ))

        updated = self._repository.assign_venues(tuple(assignments))
        return EquityVenueSyncResult(
            received_listings=len(catalog.listings),
            instrument_count=len(instruments),
            matched_instruments=matched,
            updated_instruments=updated,
            unchanged_instruments=unchanged,
            unresolved_symbols=tuple(unresolved),
            ambiguous_symbols=tuple(ambiguous),
        )


def _exact_symbol_key(value: str) -> str:
    return " ".join(value.upper().strip().split())


def _loose_symbol_key(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper().strip())
