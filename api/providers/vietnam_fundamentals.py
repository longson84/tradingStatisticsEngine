"""Vnstock generation 5 fundamental-ratio acquisition."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from importlib import import_module, metadata
from typing import Callable

import pandas as pd

from api.config import load_env_file
from api.providers.vietnam_market import ProviderDataError, ProviderUnavailableError


@dataclass(frozen=True)
class VietnamFundamentalMetadata:
    package: str
    package_version: str
    quant_package: str
    quant_package_version: str
    access_mode: str
    upstream_source: str
    method: str
    symbol: str


@dataclass(frozen=True)
class VietnamFundamentalResult:
    ratios: pd.DataFrame
    acquired_at: datetime
    metadata: VietnamFundamentalMetadata


class VnstockFundamentalProvider:
    """Compute normalized quarterly ratios through the public Gen 5 API."""

    package = "vnstock"
    quant_package = "vnstock-quant"
    access_mode = "sponsored"
    source = "VCI"

    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        load_env_file()
        self._clock = clock or (lambda: datetime.now(UTC))
        self.package_version = _package_version(self.package)
        self.quant_package_version = _package_version(self.quant_package)

    def fetch(self, symbol: str) -> VietnamFundamentalResult:
        normalized = symbol.upper().strip()
        if not normalized:
            raise ValueError("Vietnam fundamental symbol must not be empty")
        acquired_at = self._clock()
        if not isinstance(acquired_at, datetime):
            raise ProviderDataError("Vnstock acquisition timestamp is invalid")
        if acquired_at.tzinfo is None:
            acquired_at = acquired_at.replace(tzinfo=UTC)
        else:
            acquired_at = acquired_at.astimezone(UTC)
        try:
            quant_module = import_module("vnstock_quant")
            vnstock_module = import_module("vnstock")
            dataset_factory = quant_module.Dataset
            ratio_api = quant_module.fa.ratios
            fundamental = vnstock_module.Fundamental().equity(normalized)
            market = vnstock_module.Market().equity(normalized)
        except (ImportError, AttributeError) as exc:
            raise ProviderUnavailableError(
                "vnstock generation 5 and vnstock-quant 0.4.x could not be loaded"
            ) from exc
        source = self.source.lower()
        statements = [
            getattr(fundamental, report)(
                None,
                period="quarter",
                source=source,
                drop_empty=False,
            )
            for report in ("income_statement", "balance_sheet", "cash_flow")
        ]
        trade_frames = [
            market.trade_history(start=start, end=end, source=source)
            for start, end in _price_windows(acquired_at.date())
        ]
        usable_trade_frames = [
            frame for frame in trade_frames
            if isinstance(frame, pd.DataFrame) and not frame.empty
        ]
        prices = (
            pd.concat(usable_trade_frames, ignore_index=True)
            .drop_duplicates("trading_date", keep="last")
            .sort_values("trading_date")
            if usable_trade_frames
            else pd.DataFrame(columns=["trading_date", "close", "total_shares"])
        )
        dataset = dataset_factory.from_frames(
            {normalized: statements},
            {normalized: prices},
        )
        ratios = ratio_api(
            dataset,
            period="quarter",
            profile="vn",
            format="long",
        )
        if not isinstance(ratios, pd.DataFrame) or ratios.empty:
            raise ProviderDataError(
                f"vnstock-quant returned no ratios for {normalized}"
            )
        return VietnamFundamentalResult(
            ratios=ratios.copy(),
            acquired_at=acquired_at,
            metadata=VietnamFundamentalMetadata(
                package=self.package,
                package_version=self.package_version,
                quant_package=self.quant_package,
                quant_package_version=self.quant_package_version,
                access_mode=self.access_mode,
                upstream_source=self.source,
                method="quarterly_quant_ratios",
                symbol=normalized,
            ),
        )


def fundamental_source_label(metadata: VietnamFundamentalMetadata) -> str:
    """Return the stable upstream identity used by fundamental upserts."""
    return metadata.upstream_source.lower()


def fundamental_methodology(metadata: VietnamFundamentalMetadata) -> str:
    return (
        "Latest complete VCI quarterly ratios observed after acquisition; "
        f"acquired via {metadata.package} {metadata.package_version} and "
        f"{metadata.quant_package} {metadata.quant_package_version}"
    )


def fundamental_request_cost(as_of: date | None = None) -> int:
    """Return the outbound SDK calls made by one fundamental refresh."""
    return 3 + len(_price_windows(as_of or datetime.now(UTC).date()))


def _price_windows(
    end: date,
    *,
    start: date = date(2017, 1, 1),
) -> list[tuple[str, str]]:
    """Split an inclusive range into the provider's three-year windows."""
    if end < start:
        return []
    cursor = pd.Timestamp(start)
    final = pd.Timestamp(end)
    windows: list[tuple[str, str]] = []
    while cursor <= final:
        window_end = min(
            cursor + pd.DateOffset(years=3) - pd.Timedelta(days=1),
            final,
        )
        windows.append((cursor.date().isoformat(), window_end.date().isoformat()))
        cursor = window_end + pd.Timedelta(days=1)
    return windows


def _package_version(package: str) -> str:
    try:
        return metadata.version(package)
    except metadata.PackageNotFoundError:
        return "unknown"
