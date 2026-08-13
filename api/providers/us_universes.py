"""Live adapters for current United States company universes."""
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
ISHARES_IWM_URL = (
    "https://www.blackrock.com/us/individual/products/239710/"
    "ishares-russell-2000-etf/1464253357814.ajax"
    "?fileType=csv&fileName=IWM_holdings&dataType=fund"
)
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
                ticker=row.get("symbol"),
                market="US",
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
            market="US",
            description="Current Nasdaq-100 constituents from Nasdaq.",
            effective_date=_parse_provider_date(data.get("date")),
            fetched_at=datetime.now(timezone.utc),
            source="nasdaq-quote-list",
            constituents=validated_constituents(constituents, universe=code),
        )


class IsharesRussell2000UniverseProvider:
    """Use listed-equity IWM holdings as a practical Russell 2000 proxy."""

    supported_universes = frozenset({"US2000"})

    def __init__(self, fetcher: HttpFetcher = _fetch_bytes) -> None:
        self._fetcher = fetcher

    def fetch(self, universe: str) -> UniverseSnapshot:
        code = universe.upper().strip()
        if code not in self.supported_universes:
            raise UnsupportedUniverseError(f"iShares does not provide {universe!r}")
        content = self._fetcher(ISHARES_IWM_URL, None)
        text = _decode_text(content)
        if text.lstrip().lower().startswith("<!doctype html"):
            raise UniverseProviderDataError(
                "iShares returned an HTML product page instead of holdings CSV"
            )
        effective_date, constituents = _parse_ishares_csv(text)
        return UniverseSnapshot(
            code=code,
            name="Russell 2000",
            market="US",
            description=(
                "Current listed-equity holdings of IWM used as a practical "
                "Russell 2000 constituent proxy."
            ),
            effective_date=effective_date,
            fetched_at=datetime.now(timezone.utc),
            source="ishares-iwm-holdings",
            constituents=validated_constituents(constituents, universe=code),
        )


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
                ticker=row["Symbol"],
                market="US",
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
            market="US",
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
            ticker=ticker,
            market="US",
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
