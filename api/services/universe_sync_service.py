"""Fetch, validate, and persist current equity Universe membership."""
from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import replace
from datetime import UTC, datetime

from api.providers.nasdaq_symbol_directory import USListingVenueCatalog
from api.providers.universe import UniverseProviderRegistry, UniverseSnapshot
from api.providers.universe_venues import (
    needs_us_listing_catalog,
    resolve_snapshot_venues,
)
from api.repositories.universe_sync_repository import (
    UniverseSyncIdentifier,
    UniverseSyncMember,
    UniverseSyncRepository,
    UniverseSyncResult,
    UniverseSyncSnapshot,
)


US_UNIVERSE_ORDER = ("US500", "US30", "US100", "US2000")
VN_UNIVERSE_FAMILY = ("VN30", "VNMID", "VN100", "VNSML", "VNALL")
ALL_UNIVERSE_ORDER = (*US_UNIVERSE_ORDER, *VN_UNIVERSE_FAMILY)


class UniverseSyncService:
    def __init__(
        self,
        repository: UniverseSyncRepository,
        providers: UniverseProviderRegistry,
        *,
        us_listing_catalog_fetcher: Callable[[], USListingVenueCatalog],
    ) -> None:
        self._repository = repository
        self._providers = providers
        self._us_listing_catalog_fetcher = us_listing_catalog_fetcher

    def synchronize(
        self,
        universe_codes: Iterable[str],
        *,
        dry_run: bool = False,
        force: bool = False,
    ) -> tuple[UniverseSyncResult, ...]:
        requested = self.expand_universe_codes(universe_codes)
        started_at = datetime.now(UTC)
        try:
            provider_snapshots = tuple(
                self._providers.fetch(code) for code in requested
            )
            self._validate_vietnam_relationships(provider_snapshots)
            catalog = (
                self._us_listing_catalog_fetcher()
                if any(needs_us_listing_catalog(row) for row in provider_snapshots)
                else None
            )
            snapshots = tuple(
                self._to_write_snapshot(
                    resolve_snapshot_venues(row, us_catalog=catalog)
                )
                for row in provider_snapshots
            )
            if dry_run:
                return tuple(
                    replace(result, dry_run=True)
                    for result in self._repository.preview(
                        snapshots,
                        force=force,
                    )
                )
            return self._repository.synchronize(
                snapshots,
                force=force,
                started_at=started_at,
            )
        except Exception as exc:
            if not dry_run:
                self._repository.record_failures(
                    universe_codes=requested,
                    source="live-universe-provider",
                    started_at=started_at,
                    error=str(exc),
                )
            raise

    def expand_universe_codes(
        self,
        universe_codes: Iterable[str],
    ) -> tuple[str, ...]:
        normalized = {str(code).upper().strip() for code in universe_codes}
        if not normalized:
            raise ValueError("At least one Universe must be selected")
        unsupported = normalized - self._providers.supported_universes
        if unsupported:
            raise ValueError(f"Unsupported Universes: {sorted(unsupported)}")
        if normalized.intersection(VN_UNIVERSE_FAMILY):
            normalized.update(VN_UNIVERSE_FAMILY)
        return tuple(code for code in ALL_UNIVERSE_ORDER if code in normalized)

    @staticmethod
    def _validate_vietnam_relationships(
        snapshots: tuple[UniverseSnapshot, ...],
    ) -> None:
        by_code = {row.code: row for row in snapshots}
        if not set(VN_UNIVERSE_FAMILY).issubset(by_code):
            return
        members = {
            code: {row.canonical_symbol for row in by_code[code].constituents}
            for code in VN_UNIVERSE_FAMILY
        }
        if members["VN100"] != members["VN30"] | members["VNMID"]:
            raise ValueError("VN100 must equal VN30 union VNMID")
        if members["VNALL"] != members["VN100"] | members["VNSML"]:
            raise ValueError("VNALL must equal VN100 union VNSML")

    @staticmethod
    def _to_write_snapshot(snapshot: UniverseSnapshot) -> UniverseSyncSnapshot:
        return UniverseSyncSnapshot(
            code=snapshot.code,
            name=snapshot.name,
            country_code=snapshot.country_code,
            description=snapshot.description,
            effective_date=snapshot.effective_date,
            fetched_at=snapshot.fetched_at,
            source=snapshot.source,
            members=tuple(
                UniverseSyncMember(
                    symbol=row.canonical_symbol,
                    listing_symbol=row.listing_symbol,
                    company_name=row.company_name,
                    sector=row.sector,
                    industry=row.industry,
                    venue_code=str(row.exchange),
                    identifiers=tuple(
                        UniverseSyncIdentifier(value.namespace, value.value)
                        for value in row.company_identifiers
                    ),
                )
                for row in snapshot.constituents
            ),
        )
