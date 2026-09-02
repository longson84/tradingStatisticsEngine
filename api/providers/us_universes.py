"""Live adapters for current United States equity Universes."""
from __future__ import annotations

import csv
from datetime import date, datetime, timezone
from io import StringIO
import json
from typing import Callable, Mapping

import httpx
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


HttpFetcher = Callable[[str, Mapping[str, str] | None], bytes]
NASDAQ_100_URL = "https://api.nasdaq.com/api/quote/list-type/nasdaq100"
ISHARES_RUSSELL_URLS = {
    "US1000": (
        "https://www.blackrock.com/us/individual/products/239707/"
        "ishares-russell-1000-etf/latest-holdings.csv"
    ),
    "US2000": (
        "https://www.blackrock.com/us/individual/products/239710/"
        "ishares-russell-2000-etf/latest-holdings.csv"
    ),
}
WIKIPEDIA_SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
WIKIPEDIA_DOW_URL = "https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average"
_ISHARES_TICKER_OVERRIDES = {
    "MOGA": "MOG-A",
    "GEFB": "GEF-B",
    "CRDA": "CRD-A",
    "BHA": "BH-A",
}


def _fetch_bytes(url: str, params: Mapping[str, str] | None = None) -> bytes:
    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=30,
            headers={
                "Accept": "application/json,text/csv,text/html;q=0.9,*/*;q=0.8",
                "User-Agent": "Mozilla/5.0 trading-statistics-engine/0.1",
            },
        ) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            return response.content
    except httpx.HTTPError as exc:
        raise UniverseProviderUnavailableError(
            f"Unable to fetch universe data from {url}"
        ) from exc


def _parse_provider_date(value: object) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    for format_string in ("%b %d, %Y", "%B %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, format_string).date()
        except ValueError:
            continue
    return None


class Nasdaq100UniverseProvider:
    supported_universes = frozenset({"US100"})

    def __init__(self, fetcher: HttpFetcher = _fetch_bytes) -> None:
        self._fetcher = fetcher

    def fetch(self, universe: str) -> UniverseSnapshot:
        code = universe.upper().strip()
        if code not in self.supported_universes:
            raise UnsupportedUniverseError(f"Nasdaq does not provide {universe!r}")
        try:
            payload = json.loads(self._fetcher(NASDAQ_100_URL, None))
            data = payload["data"]
            rows = data.get("rows") or data["data"]["rows"]
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise UniverseProviderDataError(
                "Nasdaq-100 response is not a valid constituent payload"
            ) from exc
        constituents = [
            make_constituent(
                symbol=row.get("symbol"),
                listing_country_code="US",
                company_name=row.get("companyName"),
                sector=row.get("sector"),
                exchange="NASDAQ",
                company_identifiers=tuple(
                    identifier
                    for identifier in (make_identifier("sec_cik", row.get("cik")),)
                    if identifier is not None
                ),
            )
            for row in rows
        ]
        return UniverseSnapshot(
            code=code,
            name="Nasdaq-100",
            listing_country_code="US",
            description="Current Nasdaq-100 constituents from Nasdaq.",
            effective_date=_parse_provider_date(data.get("date")),
            fetched_at=datetime.now(timezone.utc),
            source="nasdaq-quote-list",
            constituents=validated_constituents(constituents, universe=code),
        )


class IsharesRussellUniverseProvider:
    """Use listed-equity IWB/IWM holdings as practical Russell index proxies."""

    supported_universes = frozenset({"US1000", "US2000", "US3000"})

    def __init__(self, fetcher: HttpFetcher = _fetch_bytes) -> None:
        self._fetcher = fetcher
        self._holdings_cache: dict[str, tuple[date | None, list[UniverseConstituent]]] = {}

    def fetch(self, universe: str) -> UniverseSnapshot:
        code = universe.upper().strip()
        if code not in self.supported_universes:
            raise UnsupportedUniverseError(f"iShares does not provide {universe!r}")
        if code == "US3000":
            first_date, first = self._holdings("US1000")
            second_date, second = self._holdings("US2000")
            by_symbol = {row.canonical_symbol: row for row in (*first, *second)}
            effective_date = min(
                value for value in (first_date, second_date) if value is not None
            ) if first_date or second_date else None
            constituents = list(by_symbol.values())
            fund = "IWB and IWM"
            name = "Russell 3000"
            source = "ishares-iwb-iwm-holdings-derived"
        else:
            effective_date, constituents = self._holdings(code)
            if code == "US2000" and "US1000" in self._holdings_cache:
                large_symbols = {
                    row.canonical_symbol for row in self._holdings_cache["US1000"][1]
                }
                constituents = [
                    row for row in constituents
                    if row.canonical_symbol not in large_symbols
                ]
            fund = "IWB" if code == "US1000" else "IWM"
            name = "Russell 1000" if code == "US1000" else "Russell 2000"
            source = f"ishares-{fund.lower()}-holdings"
        return UniverseSnapshot(
            code=code,
            name=name,
            listing_country_code="US",
            description=(
                f"Current listed-equity holdings of {fund} used as a practical "
                f"{name} constituent proxy."
            ),
            effective_date=effective_date,
            fetched_at=datetime.now(timezone.utc),
            source=source,
            constituents=validated_constituents(constituents, universe=code),
        )

    def _holdings(
        self,
        code: str,
    ) -> tuple[date | None, list[UniverseConstituent]]:
        cached = self._holdings_cache.get(code)
        if cached is not None:
            return cached
        content = self._fetcher(ISHARES_RUSSELL_URLS[code], None)
        text = _decode_text(content)
        if text.lstrip().lower().startswith("<!doctype html"):
            raise UniverseProviderDataError(
                "iShares returned an HTML product page instead of holdings CSV"
            )
        parsed = _parse_ishares_csv(text)
        self._holdings_cache[code] = parsed
        return parsed


class WikipediaUSIndexProvider:
    """Parse the current public constituent tables used by the existing app."""

    supported_universes = frozenset({"US500", "US30"})

    def __init__(self, fetcher: HttpFetcher = _fetch_bytes) -> None:
        self._fetcher = fetcher

    def fetch(self, universe: str) -> UniverseSnapshot:
        code = universe.upper().strip()
        if code == "US500":
            url = WIKIPEDIA_SP500_URL
            name = "S&P 500"
            description = "Current S&P 500 constituent table."
            source = "wikipedia-sp500"
            required_name = "Security"
        elif code == "US30":
            url = WIKIPEDIA_DOW_URL
            name = "Dow Jones Industrial Average"
            description = "Current Dow Jones Industrial Average constituent table."
            source = "wikipedia-dow30"
            required_name = "Company"
        else:
            raise UnsupportedUniverseError(
                f"Wikipedia index adapter does not provide {universe!r}"
            )
        html = _decode_text(self._fetcher(url, None))
        table = _find_constituent_table(html, required_name)
        constituents = [
            make_constituent(
                symbol=row["Symbol"],
                listing_country_code="US",
                company_name=row[required_name],
                sector=row.get("GICS Sector"),
                industry=row.get("GICS Sub-Industry") or row.get("Industry"),
                exchange=row.get("Exchange"),
                company_identifiers=tuple(
                    identifier
                    for identifier in (make_identifier("sec_cik", row.get("CIK")),)
                    if identifier is not None
                ),
            )
            for row in table.to_dict("records")
        ]
        return UniverseSnapshot(
            code=code,
            name=name,
            listing_country_code="US",
            description=description,
            effective_date=None,
            fetched_at=datetime.now(timezone.utc),
            source=source,
            constituents=validated_constituents(constituents, universe=code),
        )


def _decode_text(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise UniverseProviderDataError("Provider response could not be decoded")


def _parse_ishares_csv(
    text: str,
) -> tuple[date | None, list[UniverseConstituent]]:
    rows = list(csv.reader(StringIO(text)))
    effective_date = None
    header_index = None
    for index, row in enumerate(rows):
        if row and row[0].strip() == "Fund Holdings as of" and len(row) > 1:
            effective_date = _parse_provider_date(row[1])
        if "Ticker" in row and "Name" in row and "Asset Class" in row:
            header_index = index
            break
    if header_index is None:
        raise UniverseProviderDataError(
            "iShares holdings CSV is missing its constituent header"
        )
    headers = [column.strip() for column in rows[header_index]]
    constituents: list[UniverseConstituent] = []
    for values in rows[header_index + 1:]:
        if not values or not any(value.strip() for value in values):
            continue
        padded = values + [""] * (len(headers) - len(values))
        row = dict(zip(headers, padded, strict=False))
        if row.get("Asset Class", "").strip().lower() != "equity":
            continue
        exchange = row.get("Exchange", "").strip()
        if (
            not exchange
            or exchange == "-"
            or exchange.upper().startswith("NO MARKET")
            or "NON-NMS" in exchange.upper()
        ):
            continue
        ticker = row.get("Ticker", "").strip().upper()
        if not ticker or ticker == "-":
            continue
        ticker = _ISHARES_TICKER_OVERRIDES.get(ticker, ticker)
        constituents.append(make_constituent(
            symbol=ticker,
            listing_country_code="US",
            company_name=row.get("Name"),
            sector=row.get("Sector"),
            exchange=exchange,
        ))
    return effective_date, constituents


def _find_constituent_table(html: str, required_name: str) -> pd.DataFrame:
    try:
        tables = pd.read_html(StringIO(html))
    except (ImportError, ValueError) as exc:
        raise UniverseProviderDataError(
            "Wikipedia response contains no readable tables"
        ) from exc
    for original in tables:
        table = original.copy()
        table.columns = [_flatten_column(column) for column in table.columns]
        if {"Symbol", required_name}.issubset(table.columns):
            return table.where(pd.notna(table), None)
    raise UniverseProviderDataError(
        f"Wikipedia response is missing Symbol and {required_name} columns"
    )


def _flatten_column(column: object) -> str:
    if isinstance(column, tuple):
        values = [
            str(value).strip()
            for value in column
            if value and not str(value).startswith("Unnamed")
        ]
        return values[-1] if values else ""
    return str(column).strip()
