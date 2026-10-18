"""Vnstock generation 5 fundamental-ratio acquisition."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
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
        try:
            module = import_module("vnstock_quant")
            dataset_factory = module.Dataset
            ratio_api = module.fa.ratios
        except (ImportError, AttributeError) as exc:
            raise ProviderUnavailableError(
                "vnstock-quant 0.4.x could not be loaded"
            ) from exc
        dataset = dataset_factory.load(
            normalized,
            period="quarter",
            prices=True,
            notes=False,
            source=self.source.lower(),
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
        acquired_at = self._clock()
        if not isinstance(acquired_at, datetime):
            raise ProviderDataError("Vnstock acquisition timestamp is invalid")
        if acquired_at.tzinfo is None:
            acquired_at = acquired_at.replace(tzinfo=UTC)
        else:
            acquired_at = acquired_at.astimezone(UTC)
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


def _package_version(package: str) -> str:
    try:
        return metadata.version(package)
    except metadata.PackageNotFoundError:
        return "unknown"
