"""VNStock KBS adapters for current Vietnam company universes."""
from __future__ import annotations

from datetime import datetime, timezone
from importlib import import_module
from typing import Callable

import pandas as pd

from api.providers.universe import (
    UnsupportedUniverseError,
    UniverseConstituent,
    UniverseProviderDataError,
    UniverseProviderUnavailableError,
    UniverseSnapshot,
    make_constituent,
    make_identifier,
    validated_constituents,
)


ListingFactory = Callable[[], object]
_BASE_GROUPS = {
    "VN30": "VN30",
    "VNMID": "VNMidCap",
    "VNSML": "VNSmallCap",
}
_UNIVERSE_NAMES = {
    "VN30": "VN30 Index",
    "VNMID": "VNMidCap Index",
    "VN100": "VN100 Index",
    "VNSML": "VNSmallCap Index",
    "VNALL": "VNAllshare Index",
}
_SECTOR_BY_INDUSTRY_CODE = {
    1: "Wholesale",
    2: "Insurance",
    3: "Real Estate",
    5: "Securities",
    6: "Information Technology",
    7: "Retail",
    8: "Health Care",
    10: "Mining",
    11: "Banking",
    12: "Agriculture, Forestry & Fisheries",
    15: "Machinery & Equipment Manufacturing",
    16: "Household Goods Manufacturing",
    17: "Rubber Products",
    18: "Plastics & Chemicals",
    19: "Food & Beverage",
    20: "Seafood Processing",
    21: "Construction Materials",
    22: "Utilities",
    23: "Transportation & Warehousing",
    24: "Construction",
    25: "Hospitality & Entertainment",
    26: "Supporting Manufacturing",
    27: "Electrical Equipment",
    28: "Consulting & Support Services",
    29: "Other Financial Services",
}


def _default_listing_factory() -> object:
    try:
        module = import_module("vnstock")
        return module.Listing(source="KBS", show_log=False)
    except Exception as exc:
        raise UniverseProviderUnavailableError(
            "VNStock KBS listing provider could not be loaded"
        ) from exc


class VnstockUniverseProvider:
    """Fetch three disjoint KBS segments and derive their composite universes."""

    supported_universes = frozenset({
        "VN30", "VNMID", "VN100", "VNSML", "VNALL",
    })

    def __init__(self, listing_factory: ListingFactory = _default_listing_factory) -> None:
        self._listing_factory = listing_factory
        self._listing: object | None = None
        self._metadata: dict[
            str, tuple[str | None, int | None, str | None, str | None]
        ] | None = None
        self._snapshots: dict[str, UniverseSnapshot] = {}

    def fetch(self, universe: str) -> UniverseSnapshot:
        code = universe.upper().strip()
        if code not in self.supported_universes:
            raise UnsupportedUniverseError(f"VNStock does not provide {universe!r}")
        if code in self._snapshots:
            return self._snapshots[code]
        if code in _BASE_GROUPS:
            snapshot = self._fetch_base(code)
        elif code == "VN100":
            snapshot = self._combine(code, ("VN30", "VNMID"))
        else:
            snapshot = self._combine(code, ("VN30", "VNMID", "VNSML"))
        self._snapshots[code] = snapshot
        return snapshot

    def _fetch_base(self, code: str) -> UniverseSnapshot:
        listing = self._get_listing()
        try:
            raw = listing.symbols_by_group(_BASE_GROUPS[code])
        except Exception as exc:
            raise UniverseProviderUnavailableError(
                f"VNStock KBS could not fetch {code} membership"
            ) from exc
        symbols = _extract_symbols(raw, universe=code)
        metadata = self._get_metadata()
        constituents = []
        for symbol in symbols:
            name, industry_code, industry_name, organ_code = metadata.get(
                str(symbol).upper().strip(), (None, None, None, None)
            )
            constituents.append(make_constituent(
                symbol=symbol,
                country_code="VN",
                company_name=name,
                sector=_SECTOR_BY_INDUSTRY_CODE.get(industry_code),
                industry=industry_name,
                exchange="HOSE",
                company_identifiers=tuple(
                    identifier
                    for identifier in (
                        make_identifier("vnstock_organ_code", organ_code),
                    )
                    if identifier is not None
                ),
            ))
        return UniverseSnapshot(
            code=code,
            name=_UNIVERSE_NAMES[code],
            country_code="VN",
            description=f"Current {code} constituents from VNStock KBS.",
            effective_date=None,
            fetched_at=datetime.now(timezone.utc),
            source="vnstock-kbs",
            constituents=validated_constituents(constituents, universe=code),
        )

    def _combine(self, code: str, members: tuple[str, ...]) -> UniverseSnapshot:
        bases = [self.fetch(member) for member in members]
        combined = {
            value.canonical_symbol: value
            for snapshot in bases
            for value in snapshot.constituents
        }
        return UniverseSnapshot(
            code=code,
            name=_UNIVERSE_NAMES[code],
            country_code="VN",
            description=f"Derived current {code} constituents from VNStock KBS.",
            effective_date=None,
            fetched_at=max(snapshot.fetched_at for snapshot in bases),
            source="vnstock-kbs-derived",
            constituents=validated_constituents(
                list(combined.values()), universe=code
            ),
        )

    def _get_listing(self) -> object:
        if self._listing is None:
            self._listing = self._listing_factory()
        return self._listing

    def _get_metadata(
        self,
    ) -> dict[str, tuple[str | None, int | None, str | None, str | None]]:
        if self._metadata is not None:
            return self._metadata
        listing = self._get_listing()
        try:
            names = listing.all_symbols()
            industries = listing.symbols_by_industries()
        except Exception as exc:
            raise UniverseProviderUnavailableError(
                "VNStock KBS could not fetch company metadata"
            ) from exc
        if not isinstance(names, pd.DataFrame) or "symbol" not in names:
            raise UniverseProviderDataError(
                "VNStock all_symbols response is missing symbol metadata"
            )
        name_by_symbol = {
            str(row["symbol"]).upper().strip(): (
                _optional_frame_value(row.get("organ_name")),
                _optional_frame_value(row.get("organ_code")),
            )
            for row in names.to_dict("records")
        }
        industry_by_symbol: dict[str, tuple[int | None, str | None]] = {}
        if isinstance(industries, pd.DataFrame) and "symbol" in industries:
            for row in industries.to_dict("records"):
                raw_code = row.get("industry_code")
                try:
                    industry_code = int(raw_code) if pd.notna(raw_code) else None
                except (TypeError, ValueError):
                    industry_code = None
                industry_by_symbol[str(row["symbol"]).upper().strip()] = (
                    industry_code,
                    _optional_frame_value(row.get("industry_name")),
                )
        self._metadata = {
            symbol: (
                name_and_code[0],
                industry_by_symbol.get(symbol, (None, None))[0],
                industry_by_symbol.get(symbol, (None, None))[1],
                name_and_code[1],
            )
            for symbol, name_and_code in name_by_symbol.items()
        }
        return self._metadata


def _extract_symbols(value: object, *, universe: str) -> list[object]:
    if isinstance(value, pd.Series):
        return value.dropna().tolist()
    if isinstance(value, pd.DataFrame) and "symbol" in value:
        return value["symbol"].dropna().tolist()
    if isinstance(value, (list, tuple, set)):
        return list(value)
    raise UniverseProviderDataError(
        f"VNStock {universe} response is not a symbol collection"
    )


def _optional_frame_value(value: object) -> str | None:
    if value is None or not pd.notna(value):
        return None
    text = str(value).strip()
    return text or None
