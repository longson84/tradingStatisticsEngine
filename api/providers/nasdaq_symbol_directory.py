"""Official Nasdaq Trader symbol-directory adapter for US listing venues."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import UTC, datetime
from io import StringIO

import httpx


NASDAQ_TRADER_BASE_URL = "https://www.nasdaqtrader.com"
NASDAQ_SYMBOL_DIRECTORY_SOURCE = "nasdaq_trader_symbol_directory"

_OTHER_EXCHANGE_CODES = {
    "A": "NYSE_AMERICAN",
    "N": "NYSE",
    "P": "NYSE_ARCA",
    "Z": "CBOE_BZX",
    "V": "IEX",
}


class NasdaqSymbolDirectoryError(RuntimeError):
    """The official symbol directory was unavailable or malformed."""


@dataclass(frozen=True)
class USListingVenue:
    primary_symbols: tuple[str, ...]
    alternate_symbols: tuple[str, ...]
    venue_code: str


@dataclass(frozen=True)
class USListingVenueCatalog:
    listings: tuple[USListingVenue, ...]
    fetched_at: datetime
    source: str = NASDAQ_SYMBOL_DIRECTORY_SOURCE


class NasdaqSymbolDirectoryClient:
    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        base_url: str = NASDAQ_TRADER_BASE_URL,
        timeout: float = 30.0,
    ) -> None:
        self._client = client or httpx.Client(
            base_url=base_url,
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "trading-statistics-engine/0.1"},
        )
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> NasdaqSymbolDirectoryClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def fetch_catalog(self) -> USListingVenueCatalog:
        nasdaq_text = self._get_text(
            "/dynamic/SymDir/nasdaqlisted.txt"
        )
        other_text = self._get_text(
            "/dynamic/SymDir/otherlisted.txt"
        )
        listings = (
            *_parse_nasdaq_listed(nasdaq_text),
            *_parse_other_listed(other_text),
        )
        if len(listings) < 1_000:
            raise NasdaqSymbolDirectoryError(
                "Nasdaq Trader returned an implausibly small US listing catalog"
            )
        return USListingVenueCatalog(
            listings=tuple(listings),
            fetched_at=datetime.now(UTC),
        )

    def _get_text(self, path: str) -> str:
        try:
            response = self._client.get(path)
            response.raise_for_status()
            return response.text
        except httpx.HTTPError as exc:
            raise NasdaqSymbolDirectoryError(
                f"Nasdaq Trader request failed for {path}: {exc}"
            ) from exc


def _parse_nasdaq_listed(payload: str) -> tuple[USListingVenue, ...]:
    rows = csv.DictReader(StringIO(payload), delimiter="|")
    if rows.fieldnames is None or not {"Symbol", "Test Issue"}.issubset(rows.fieldnames):
        raise NasdaqSymbolDirectoryError("nasdaqlisted.txt has an unexpected header")
    parsed = []
    for row in rows:
        symbol = _symbol(row.get("Symbol"))
        if symbol is None or row.get("Test Issue") != "N":
            continue
        parsed.append(USListingVenue(
            primary_symbols=(symbol,),
            alternate_symbols=(),
            venue_code="NASDAQ",
        ))
    return tuple(parsed)


def _parse_other_listed(payload: str) -> tuple[USListingVenue, ...]:
    rows = csv.DictReader(StringIO(payload), delimiter="|")
    required = {"ACT Symbol", "Exchange", "Test Issue", "NASDAQ Symbol"}
    if rows.fieldnames is None or not required.issubset(rows.fieldnames):
        raise NasdaqSymbolDirectoryError("otherlisted.txt has an unexpected header")
    parsed = []
    for row in rows:
        venue_code = _OTHER_EXCHANGE_CODES.get(str(row.get("Exchange") or ""))
        if venue_code is None or row.get("Test Issue") != "N":
            continue
        primary_symbols = tuple(dict.fromkeys(
            value
            for value in (
                _symbol(row.get("ACT Symbol")),
                _symbol(row.get("NASDAQ Symbol")),
            )
            if value is not None
        ))
        alternate_symbols = tuple(
            value
            for value in (_symbol(row.get("CQS Symbol")),)
            if value is not None and value not in primary_symbols
        )
        if primary_symbols:
            parsed.append(USListingVenue(
                primary_symbols=primary_symbols,
                alternate_symbols=alternate_symbols,
                venue_code=venue_code,
            ))
    return tuple(parsed)


def _symbol(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).upper().strip()
    if not normalized or normalized.startswith("FILE CREATION TIME"):
        return None
    return normalized
