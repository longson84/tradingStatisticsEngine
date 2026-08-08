"""Typed adapters for sponsored and community Vietnam market data."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from importlib import import_module, metadata, util
from typing import Literal, Protocol

import pandas as pd

from api.config import load_env_file


AccessMode = Literal["sponsored", "community"]


class ProviderUnavailableError(RuntimeError):
    """Raised when the selected provider package cannot be loaded."""


class ProviderDataError(RuntimeError):
    """Raised when a provider returns no usable data for a request."""


class UnsupportedProviderMethodError(RuntimeError):
    """Raised when an access mode does not expose the requested dataset."""


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
    ) -> VietnamProviderResult: ...

    def trade_history(
        self,
        symbol: str,
        start: date,
        end: date,
    ) -> VietnamProviderResult: ...


class VnstockDataProvider:
    """Sponsored Unified UI adapter.

    Unified UI performs method-specific KBS/VCI routing internally. Until the
    package exposes the selected upstream in its result, provenance records the
    source honestly as ``unified`` rather than guessing KBS or VCI.
    """

    package = "vnstock_data"
    access_mode: AccessMode = "sponsored"

    def __init__(self) -> None:
        load_env_file()

    def ohlcv(
        self,
        symbol: str,
        start: date,
        end: date,
        *,
        interval: str = "1D",
    ) -> VietnamProviderResult:
        normalized = _request(symbol, start, end)
        equity = self._market().equity(normalized)
        frame = equity.ohlcv(
            start=start.isoformat(),
            end=end.isoformat(),
            interval=interval,
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
        )
        return self._result(frame, normalized, start, end, "trade_history")

    def _market(self):
        try:
            module = import_module(self.package)
            return module.Market()
        except Exception as exc:
            raise ProviderUnavailableError(
                "vnstock_data could not be loaded or authenticated"
            ) from exc

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
                package_version=_package_version(self.package),
                access_mode=self.access_mode,
                upstream_source="unified",
                method=method,
                symbol=symbol,
                requested_start=start,
                requested_end=end,
            ),
        )


class CommunityVnstockProvider:
    """Community OHLCV fallback used only when the sponsor package is absent."""

    package = "vnstock"
    access_mode: AccessMode = "community"

    def __init__(self, source: str = "KBS") -> None:
        self.source = source.upper().strip()

    def ohlcv(
        self,
        symbol: str,
        start: date,
        end: date,
        *,
        interval: str = "1D",
    ) -> VietnamProviderResult:
        normalized = _request(symbol, start, end)
        try:
            module = import_module(self.package)
            frame = module.Quote(symbol=normalized, source=self.source).history(
                start=start.isoformat(),
                end=end.isoformat(),
                interval=interval,
            )
        except Exception as exc:
            raise ProviderUnavailableError(
                "community vnstock could not be loaded"
            ) from exc
        return VietnamProviderResult(
            frame=_require_frame(frame, normalized, "ohlcv"),
            metadata=VietnamProviderMetadata(
                package=self.package,
                package_version=_package_version(self.package),
                access_mode=self.access_mode,
                upstream_source=self.source,
                method="ohlcv",
                symbol=normalized,
                requested_start=start,
                requested_end=end,
            ),
        )

    def trade_history(
        self,
        symbol: str,
        start: date,
        end: date,
    ) -> VietnamProviderResult:
        _request(symbol, start, end)
        raise UnsupportedProviderMethodError(
            "trade_history requires the sponsored vnstock_data package"
        )


def create_vietnam_market_provider(
    *,
    require_sponsored: bool = False,
    community_source: str = "KBS",
) -> VietnamMarketProvider:
    """Prefer sponsored access and fall back only when its package is absent."""
    load_env_file()
    if util.find_spec("vnstock_data") is not None:
        return VnstockDataProvider()
    if require_sponsored:
        raise ProviderUnavailableError(
            "vnstock_data is not installed; use the official sponsor installer"
        )
    return CommunityVnstockProvider(source=community_source)


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
