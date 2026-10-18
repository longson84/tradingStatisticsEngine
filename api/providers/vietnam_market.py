"""Typed adapter for authenticated sponsored Vietnam market data."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from importlib import import_module, metadata
from typing import Literal, Protocol

import pandas as pd

from api.config import load_env_file


AccessMode = Literal["sponsored"]
InstrumentKind = Literal["equity", "index"]


class ProviderUnavailableError(RuntimeError):
    """Raised when the selected provider package cannot be loaded."""


class ProviderDataError(RuntimeError):
    """Raised when a provider returns no usable data for a request."""


@dataclass(frozen=True)
class VietnamProviderMetadata:
    package: str
    package_version: str
    access_mode: AccessMode
    upstream_source: str
    method: str
    symbol: str
    requested_start: date
    requested_end: date


@dataclass(frozen=True)
class VietnamProviderResult:
    frame: pd.DataFrame
    metadata: VietnamProviderMetadata


class VietnamMarketProvider(Protocol):
    def ohlcv(
        self,
        symbol: str,
        start: date,
        end: date,
        *,
        interval: str = "1D",
        instrument_kind: InstrumentKind = "equity",
    ) -> VietnamProviderResult: ...

    def trade_history(
        self,
        symbol: str,
        start: date,
        end: date,
    ) -> VietnamProviderResult: ...


class VnstockProvider:
    """Vnstock generation 5 adapter using explicit VCI market routes."""

    package = "vnstock"
    access_mode: AccessMode = "sponsored"
    source = "VCI"

    def __init__(self) -> None:
        load_env_file()
        self.package_version = _package_version(self.package)
        if not self.package_version.startswith("5.1."):
            raise ProviderUnavailableError(
                "VnstockProvider requires vnstock 5.1.x in its runtime"
            )

    def ohlcv(
        self,
        symbol: str,
        start: date,
        end: date,
        *,
        interval: str = "1D",
        instrument_kind: InstrumentKind = "equity",
    ) -> VietnamProviderResult:
        normalized = _request(symbol, start, end)
        market = self._market()
        instrument = (
            market.index(normalized)
            if instrument_kind == "index"
            else market.equity(normalized)
        )
        frame = instrument.ohlcv(
            start=start.isoformat(),
            end=end.isoformat(),
            interval=interval,
            source=self.source.lower(),
        )
        return self._result(frame, normalized, start, end, "ohlcv")

    def trade_history(
        self,
        symbol: str,
        start: date,
        end: date,
    ) -> VietnamProviderResult:
        normalized = _request(symbol, start, end)
        frame = self._market().equity(normalized).trade_history(
            start=start.isoformat(),
            end=end.isoformat(),
            source=self.source.lower(),
        )
        return self._result(frame, normalized, start, end, "trade_history")

    def _market(self):
        try:
            module = import_module(self.package)
            market_factory = module.Market
        except (ImportError, AttributeError) as exc:
            raise ProviderUnavailableError(
                "vnstock generation 5 could not be loaded"
            ) from exc
        return market_factory()

    def _result(
        self,
        frame: pd.DataFrame | None,
        symbol: str,
        start: date,
        end: date,
        method: str,
    ) -> VietnamProviderResult:
        clean = _require_frame(frame, symbol, method)
        return VietnamProviderResult(
            frame=clean,
            metadata=VietnamProviderMetadata(
                package=self.package,
                package_version=self.package_version,
                access_mode=self.access_mode,
                upstream_source=self.source,
                method=method,
                symbol=symbol,
                requested_start=start,
                requested_end=end,
            ),
        )


def provider_source_label(metadata: VietnamProviderMetadata) -> str:
    """Build stable row provenance without claiming an unknown upstream."""
    package = metadata.package.replace("_", "-").lower()
    upstream = metadata.upstream_source.replace("_", "-").lower()
    return f"{package}-{metadata.package_version}-{upstream}"


def normalize_ohlcv_result(result: VietnamProviderResult) -> pd.DataFrame:
    """Normalize a provider OHLCV result for canonical price persistence."""
    frame = result.frame.copy()
    frame.columns = [str(column).lower() for column in frame.columns]
    if "time" in frame.columns:
        frame = frame.rename(columns={"time": "date"})
    elif "date" not in frame.columns:
        raise ProviderDataError(
            f"ohlcv data for {result.metadata.symbol} is missing a date column"
        )
    required = {"date", "open", "high", "low", "close"}
    missing = required - set(frame.columns)
    if missing:
        raise ProviderDataError(
            f"ohlcv data for {result.metadata.symbol} is missing columns: "
            f"{sorted(missing)}"
        )
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    for column in ("open", "high", "low", "close", "volume"):
        if column not in frame:
            frame[column] = pd.NA
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["symbol"] = result.metadata.symbol
    frame["provider_source"] = provider_source_label(result.metadata)
    return (
        frame[[
            "symbol", "date", "open", "high", "low", "close", "volume",
            "provider_source",
        ]]
        .dropna(subset=["date", "open", "high", "low", "close"])
        .sort_values("date")
        .drop_duplicates("date", keep="last")
        .reset_index(drop=True)
    )


def _request(symbol: str, start: date, end: date) -> str:
    normalized = symbol.upper().strip()
    if not normalized:
        raise ValueError("Vietnam market symbol must not be empty")
    if start > end:
        raise ValueError("Vietnam market start date must not be after end date")
    return normalized


def _require_frame(
    frame: pd.DataFrame | None,
    symbol: str,
    method: str,
) -> pd.DataFrame:
    if frame is None or frame.empty:
        raise ProviderDataError(f"{method} returned no data for {symbol}")
    return frame.copy()


def _package_version(package: str) -> str:
    try:
        return metadata.version(package)
    except metadata.PackageNotFoundError:
        return "unknown"
