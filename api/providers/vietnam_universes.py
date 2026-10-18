"""Vnstock generation 5 adapter for current Vietnam equity universes."""
from __future__ import annotations

from datetime import datetime, timezone
from importlib import import_module, metadata
from typing import Callable

import pandas as pd

from api.providers.universe import (
    UnsupportedUniverseError,
    UniverseProviderDataError,
    UniverseProviderUnavailableError,
    UniverseSnapshot,
    make_constituent,
    validated_constituents,
)


ReferenceFactory = Callable[[], object]
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


def _default_reference_factory() -> object:
    try:
        module = import_module("vnstock")
        return module.Reference()
    except (ImportError, AttributeError) as exc:
        raise UniverseProviderUnavailableError(
            "Vnstock generation 5 Reference API could not be loaded"
        ) from exc


class VnstockUniverseProvider:
    """Fetch Gen 5 index segments and derive their composite universes."""

    supported_universes = frozenset({
        "VN30", "VNMID", "VN100", "VNSML", "VNALL",
    })

    def __init__(
        self,
        reference_factory: ReferenceFactory = _default_reference_factory,
    ) -> None:
        self._reference_factory = reference_factory
        self._reference: object | None = None
        self._metadata: dict[
            str, tuple[str | None, str | None, str | None, str | None]
        ] | None = None
        self._snapshots: dict[str, UniverseSnapshot] = {}

    def fetch(self, universe: str) -> UniverseSnapshot:
        code = universe.upper().strip()
        if code not in self.supported_universes:
            raise UnsupportedUniverseError(
                f"Vnstock does not provide {universe!r}"
            )
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
        reference = self._get_reference()
        try:
            raw = reference.index.list_by_group(
                _BASE_GROUPS[code], source="kbs"
            )
        except Exception as exc:
            raise UniverseProviderUnavailableError(
                f"Vnstock KBS could not fetch {code} membership"
            ) from exc
        symbols = _extract_symbols(raw, universe=code)
        metadata_by_symbol = self._get_metadata()
        constituents = []
        for symbol in symbols:
            normalized = str(symbol).upper().strip()
            name, sector, industry, exchange = metadata_by_symbol.get(
                normalized, (None, None, None, None)
            )
            constituents.append(make_constituent(
                symbol=normalized,
                listing_country_code="VN",
                company_name=name,
                sector=sector,
                industry=industry,
                exchange=exchange or "HOSE",
            ))
        return UniverseSnapshot(
            code=code,
            name=_UNIVERSE_NAMES[code],
            listing_country_code="VN",
            description=f"Current {code} constituents from Vnstock Gen 5 KBS.",
            effective_date=None,
            fetched_at=datetime.now(timezone.utc),
            source=_source_label(),
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
            listing_country_code="VN",
            description=(
                f"Derived current {code} constituents from Vnstock Gen 5 KBS."
            ),
            effective_date=None,
            fetched_at=max(snapshot.fetched_at for snapshot in bases),
            source=f"{_source_label()}-derived",
            constituents=validated_constituents(
                list(combined.values()), universe=code
            ),
        )

    def _get_reference(self) -> object:
        if self._reference is None:
            self._reference = self._reference_factory()
        return self._reference

    def _get_metadata(
        self,
    ) -> dict[str, tuple[str | None, str | None, str | None, str | None]]:
        if self._metadata is not None:
            return self._metadata
        reference = self._get_reference()
        try:
            equities = reference.equity.list_by_exchange(source="vci")
            industries = reference.equity.list_by_industry(
                lang="en", source="vci"
            )
        except Exception as exc:
            raise UniverseProviderUnavailableError(
                "Vnstock VCI could not fetch company metadata"
            ) from exc
        if not isinstance(equities, pd.DataFrame) or "symbol" not in equities:
            raise UniverseProviderDataError(
                "Vnstock equity response is missing symbol metadata"
            )
        company_by_symbol = {
            str(row["symbol"]).upper().strip(): (
                _optional_frame_value(row.get("organ_name")),
                _optional_frame_value(row.get("exchange")),
            )
            for row in equities.to_dict("records")
        }
        industry_by_symbol = _industry_metadata(industries)
        self._metadata = {
            symbol: (
                company[0],
                industry_by_symbol.get(symbol, (None, None))[0],
                industry_by_symbol.get(symbol, (None, None))[1],
                company[1],
            )
            for symbol, company in company_by_symbol.items()
        }
        return self._metadata


def _industry_metadata(
    industries: object,
) -> dict[str, tuple[str | None, str | None]]:
    required = {"symbol", "icb_level", "icb_name"}
    if not isinstance(industries, pd.DataFrame) or not required.issubset(
        industries.columns
    ):
        return {}
    result: dict[str, tuple[str | None, str | None]] = {}
    rows = industries.copy()
    rows["icb_level"] = pd.to_numeric(rows["icb_level"], errors="coerce")
    for symbol, group in rows.dropna(subset=["symbol"]).groupby("symbol"):
        ordered = group.dropna(subset=["icb_level"]).sort_values("icb_level")
        if ordered.empty:
            continue
        level_one = ordered[ordered["icb_level"] == 1]
        sector = (
            _optional_frame_value(level_one.iloc[-1].get("icb_name"))
            if not level_one.empty
            else None
        )
        industry = _optional_frame_value(ordered.iloc[-1].get("icb_name"))
        result[str(symbol).upper().strip()] = (sector, industry)
    return result


def _extract_symbols(value: object, *, universe: str) -> list[object]:
    if isinstance(value, pd.Series):
        return value.dropna().tolist()
    if isinstance(value, pd.DataFrame) and "symbol" in value:
        return value["symbol"].dropna().tolist()
    if isinstance(value, (list, tuple, set)):
        return list(value)
    raise UniverseProviderDataError(
        f"Vnstock {universe} response is not a symbol collection"
    )


def _source_label() -> str:
    try:
        version = metadata.version("vnstock")
    except metadata.PackageNotFoundError:
        version = "unknown"
    return f"vnstock-{version}-kbs"


def _optional_frame_value(value: object) -> str | None:
    if value is None or not pd.notna(value):
        return None
    text = str(value).strip()
    return text or None
