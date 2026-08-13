"""Unauthenticated Binance Spot catalog and daily-market-data adapters."""
from __future__ import annotations

from collections.abc import Iterable
import csv
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
import hashlib
from io import BytesIO, TextIOWrapper
from zipfile import BadZipFile, ZipFile

import httpx


BINANCE_SPOT_API_URL = "https://data-api.binance.vision"
BINANCE_PUBLIC_DATA_URL = "https://data.binance.vision"


class BinanceSpotProviderError(RuntimeError):
    """Binance returned an unavailable, malformed, or unverifiable payload."""


@dataclass(frozen=True)
class BinanceSpotSymbol:
    symbol: str
    status: str
    base_asset: str
    quote_asset: str
    price_tick_size: Decimal | None
    quantity_step_size: Decimal | None
    minimum_quantity: Decimal | None
    minimum_notional: Decimal | None
    is_spot_trading_allowed: bool


@dataclass(frozen=True)
class BinanceSpotCatalog:
    symbols: tuple[BinanceSpotSymbol, ...]
    fetched_at: datetime


@dataclass(frozen=True)
class BinanceDailyKline:
    symbol: str
    trading_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    open_time: datetime
    close_time: datetime
    source: str


@dataclass(frozen=True)
class BinanceArchiveMonth:
    found: bool
    klines: tuple[BinanceDailyKline, ...]


class BinanceSpotClient:
    """Small public REST client with injectable transport for deterministic tests."""

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        base_url: str = BINANCE_SPOT_API_URL,
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

    def __enter__(self) -> BinanceSpotClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def fetch_catalog(self) -> BinanceSpotCatalog:
        payload = self._get_json(
            "/api/v3/exchangeInfo",
            params={"permissions": "SPOT", "showPermissionSets": "false"},
        )
        if not isinstance(payload, dict) or not isinstance(
            payload.get("symbols"), list
        ):
            raise BinanceSpotProviderError("exchangeInfo did not contain a symbols list")
        symbols = tuple(_parse_spot_symbol(value) for value in payload["symbols"])
        if not symbols:
            raise BinanceSpotProviderError("exchangeInfo returned an empty spot catalog")
        duplicates = _duplicates(row.symbol for row in symbols)
        if duplicates:
            raise BinanceSpotProviderError(
                f"exchangeInfo returned duplicate symbols: {sorted(duplicates)}"
            )
        return BinanceSpotCatalog(symbols=symbols, fetched_at=datetime.now(UTC))

    def fetch_daily_klines(
        self,
        symbol: str,
        start: date,
        end: date,
    ) -> tuple[BinanceDailyKline, ...]:
        normalized = _symbol(symbol)
        if start > end:
            raise ValueError("Binance kline start date must not be after end date")
        start_ms = _utc_midnight_ms(start)
        end_ms = _utc_midnight_ms(end + timedelta(days=1)) - 1
        rows: list[BinanceDailyKline] = []
        next_start = start_ms
        while next_start <= end_ms:
            payload = self._get_json(
                "/api/v3/klines",
                params={
                    "symbol": normalized,
                    "interval": "1d",
                    "startTime": next_start,
                    "endTime": end_ms,
                    "limit": 1000,
                },
            )
            if not isinstance(payload, list):
                raise BinanceSpotProviderError("klines response was not a list")
            if not payload:
                break
            page = tuple(
                _parse_kline(normalized, raw, source="binance_spot_rest")
                for raw in payload
            )
            rows.extend(
                row for row in page if start <= row.trading_date <= end
            )
            following = _datetime_ms(page[-1].open_time) + 86_400_000
            if following <= next_start:
                raise BinanceSpotProviderError("klines pagination did not advance")
            next_start = following
            if len(payload) < 1000:
                break
        return tuple(_deduplicate_klines(rows))

    def _get_json(self, path: str, *, params: dict[str, object]) -> object:
        try:
            response = self._client.get(path, params=params)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise BinanceSpotProviderError(
                f"Binance Spot request failed for {path}: {exc}"
            ) from exc


class BinancePublicDataClient:
    """Checksum-verifying reader for Binance monthly public-data archives."""

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        base_url: str = BINANCE_PUBLIC_DATA_URL,
        timeout: float = 120.0,
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

    def __enter__(self) -> BinancePublicDataClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def fetch_month(self, symbol: str, month: date) -> BinanceArchiveMonth:
        normalized = _symbol(symbol)
        month_start = month.replace(day=1)
        filename = f"{normalized}-1d-{month_start:%Y-%m}.zip"
        path = (
            f"/data/spot/monthly/klines/{normalized}/1d/{filename}"
        )
        try:
            archive_response = self._client.get(path)
            if archive_response.status_code == 404:
                return BinanceArchiveMonth(found=False, klines=())
            archive_response.raise_for_status()
            checksum_response = self._client.get(f"{path}.CHECKSUM")
            checksum_response.raise_for_status()
        except httpx.HTTPError as exc:
            raise BinanceSpotProviderError(
                f"Binance public-data request failed for {filename}: {exc}"
            ) from exc
        expected = checksum_response.text.strip().split()[0].lower()
        actual = hashlib.sha256(archive_response.content).hexdigest()
        if not expected or expected != actual:
            raise BinanceSpotProviderError(
                f"Checksum mismatch for Binance archive {filename}"
            )
        try:
            with ZipFile(BytesIO(archive_response.content)) as archive:
                members = [name for name in archive.namelist() if not name.endswith("/")]
                if len(members) != 1:
                    raise BinanceSpotProviderError(
                        f"Binance archive {filename} must contain exactly one CSV"
                    )
                with archive.open(members[0]) as raw:
                    rows = _parse_archive_csv(
                        normalized, TextIOWrapper(raw, encoding="utf-8")
                    )
        except (BadZipFile, OSError, UnicodeError) as exc:
            raise BinanceSpotProviderError(
                f"Invalid Binance archive {filename}: {exc}"
            ) from exc
        return BinanceArchiveMonth(found=True, klines=tuple(rows))


class BinanceSpotHistoryLoader:
    """Use monthly archives for backfill and REST for the uncovered tail/gaps."""

    def __init__(
        self,
        rest: BinanceSpotClient,
        archive: BinancePublicDataClient | None = None,
    ) -> None:
        self._rest = rest
        self._archive = archive

    def load(
        self,
        symbol: str,
        start: date,
        end: date,
        *,
        source: str = "auto",
    ) -> tuple[BinanceDailyKline, ...]:
        if source not in {"auto", "rest", "archive"}:
            raise ValueError(f"Unsupported Binance history source: {source}")
        if start > end:
            raise ValueError("Binance history start date must not be after end date")
        if source == "rest":
            return self._rest.fetch_daily_klines(symbol, start, end)
        if self._archive is None:
            raise ValueError("Archive history requested without an archive client")

        archive_rows: list[BinanceDailyKline] = []
        found_months: list[date] = []
        missing_months: list[date] = []
        month = start.replace(day=1)
        while month <= end:
            result = self._archive.fetch_month(symbol, month)
            if result.found:
                found_months.append(month)
                archive_rows.extend(
                    row for row in result.klines if start <= row.trading_date <= end
                )
            else:
                missing_months.append(month)
            month = _next_month(month)

        if source == "archive":
            return tuple(_deduplicate_klines(archive_rows))
        if not found_months:
            return self._rest.fetch_daily_klines(symbol, start, end)

        rest_ranges: list[tuple[date, date]] = []
        first_found = min(found_months)
        last_found = max(found_months)
        for missing in missing_months:
            if first_found <= missing <= last_found:
                rest_ranges.append(
                    (max(start, missing), min(end, _next_month(missing) - timedelta(days=1)))
                )
        latest_archive_date = max(
            (row.trading_date for row in archive_rows), default=last_found
        )
        if latest_archive_date < end:
            rest_ranges.append((latest_archive_date + timedelta(days=1), end))

        rows = list(archive_rows)
        for range_start, range_end in _merge_ranges(rest_ranges):
            rows.extend(self._rest.fetch_daily_klines(symbol, range_start, range_end))
        return tuple(_deduplicate_klines(rows))


def _parse_spot_symbol(raw: object) -> BinanceSpotSymbol:
    if not isinstance(raw, dict):
        raise BinanceSpotProviderError("exchangeInfo symbol entry was not an object")
    try:
        symbol = _symbol(raw["symbol"])
        status = str(raw["status"]).upper().strip()
        base_asset = _symbol(raw["baseAsset"])
        quote_asset = _symbol(raw["quoteAsset"])
    except (KeyError, TypeError, ValueError) as exc:
        raise BinanceSpotProviderError(f"Malformed exchangeInfo symbol: {raw}") from exc
    filters = raw.get("filters")
    if not isinstance(filters, list):
        filters = []
    by_type = {
        str(value.get("filterType")): value
        for value in filters
        if isinstance(value, dict)
    }
    lot = by_type.get("LOT_SIZE", {})
    price = by_type.get("PRICE_FILTER", {})
    notional = by_type.get("NOTIONAL", by_type.get("MIN_NOTIONAL", {}))
    return BinanceSpotSymbol(
        symbol=symbol,
        status=status,
        base_asset=base_asset,
        quote_asset=quote_asset,
        price_tick_size=_optional_decimal(price.get("tickSize")),
        quantity_step_size=_optional_decimal(lot.get("stepSize")),
        minimum_quantity=_optional_decimal(lot.get("minQty")),
        minimum_notional=_optional_decimal(notional.get("minNotional")),
        is_spot_trading_allowed=bool(raw.get("isSpotTradingAllowed", True)),
    )


def _parse_kline(symbol: str, raw: object, *, source: str) -> BinanceDailyKline:
    if not isinstance(raw, (list, tuple)) or len(raw) < 7:
        raise BinanceSpotProviderError(f"Malformed Binance kline for {symbol}")
    try:
        open_time = _timestamp(raw[0])
        close_time = _timestamp(raw[6])
        return BinanceDailyKline(
            symbol=symbol,
            trading_date=open_time.date(),
            open=Decimal(str(raw[1])),
            high=Decimal(str(raw[2])),
            low=Decimal(str(raw[3])),
            close=Decimal(str(raw[4])),
            volume=Decimal(str(raw[5])),
            open_time=open_time,
            close_time=close_time,
            source=source,
        )
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise BinanceSpotProviderError(f"Malformed Binance kline for {symbol}") from exc


def _parse_archive_csv(symbol: str, handle: TextIOWrapper) -> list[BinanceDailyKline]:
    parsed: list[BinanceDailyKline] = []
    reader = csv.reader(handle)
    for row in reader:
        if not row:
            continue
        if not str(row[0]).strip().isdigit():
            continue
        parsed.append(_parse_kline(symbol, row, source="binance_public_data"))
    return parsed


def _timestamp(value: object) -> datetime:
    numeric = int(str(value))
    if numeric > 100_000_000_000_000:
        numeric //= 1000
    return datetime.fromtimestamp(numeric / 1000, tz=UTC)


def _optional_decimal(value: object) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise BinanceSpotProviderError(f"Invalid Binance decimal value: {value}") from exc


def _symbol(value: object) -> str:
    normalized = str(value).upper().strip()
    if not normalized or len(normalized) > 64 or not normalized.isalnum():
        raise ValueError(f"Invalid Binance symbol or asset code: {value!r}")
    return normalized


def _duplicates(values: Iterable[str]) -> set[str]:
    seen: set[str] = set()
    repeated: set[str] = set()
    for value in values:
        if value in seen:
            repeated.add(value)
        seen.add(value)
    return repeated


def _utc_midnight_ms(value: date) -> int:
    return int(datetime(value.year, value.month, value.day, tzinfo=UTC).timestamp() * 1000)


def _datetime_ms(value: datetime) -> int:
    return int(value.timestamp() * 1000)


def _next_month(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


def _deduplicate_klines(
    values: list[BinanceDailyKline],
) -> list[BinanceDailyKline]:
    by_date = {value.trading_date: value for value in values}
    return [by_date[key] for key in sorted(by_date)]


def _merge_ranges(values: list[tuple[date, date]]) -> list[tuple[date, date]]:
    merged: list[tuple[date, date]] = []
    for start, end in sorted(values):
        if start > end:
            continue
        if merged and start <= merged[-1][1] + timedelta(days=1):
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged
