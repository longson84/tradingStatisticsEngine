"""Sponsored Vietnam fundamental-report acquisition."""
from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module, metadata

import pandas as pd

from api.config import load_env_file
from api.providers.vietnam_market import ProviderDataError, ProviderUnavailableError


@dataclass(frozen=True)
class VietnamFundamentalMetadata:
    package: str
    package_version: str
    access_mode: str
    upstream_source: str
    method: str
    symbol: str


@dataclass(frozen=True)
class VietnamFundamentalResult:
    ratios: pd.DataFrame
    income: pd.DataFrame
    metadata: VietnamFundamentalMetadata


class VnstockDataFundamentalProvider:
    """Fetch raw quarterly VCI reports through the sponsored package.

    The package's unified ``Finance`` wrapper currently converts raw VCI date
    columns to numeric values and therefore loses ``publicDate``. Its formatted
    ratio method also removes ``quarter``, which makes gaps impossible to align
    safely. The explicit VCI adapter preserves dates through its public income
    method; its raw report hook is narrowly used for ratios until the formatted
    method retains exact fiscal-quarter identity.
    """

    package = "vnstock_data"
    package_version = "unknown"
    access_mode = "sponsored"
    source = "VCI"

    def __init__(self) -> None:
        load_env_file()
        try:
            self.package_version = metadata.version(self.package)
        except metadata.PackageNotFoundError:
            self.package_version = "unknown"

    def fetch(self, symbol: str) -> VietnamFundamentalResult:
        normalized = symbol.upper().strip()
        if not normalized:
            raise ValueError("Vietnam fundamental symbol must not be empty")
        try:
            module = import_module("vnstock_data.explorer.vci.financial")
            finance = module.Finance(
                symbol=normalized,
                period="quarter",
                get_all=True,
                show_log=False,
            )
            common = {
                "period": "quarter",
                "mode": "raw",
                "format": "wide",
                "get_all": True,
                "dropna": False,
                "show_log": False,
            }
            ratios = finance._get_report(
                report_type="ratio",
                lang="en",
                mode="raw",
                format="wide",
                value_format=False,
                get_all=True,
                show_log=False,
            )
            income = finance.income_statement(**common)
        except Exception as exc:
            raise ProviderUnavailableError(
                "vnstock_data VCI fundamentals could not be loaded or authenticated"
            ) from exc
        if ratios is None or ratios.empty:
            raise ProviderDataError(f"VCI ratio returned no data for {normalized}")
        if income is None or income.empty:
            raise ProviderDataError(
                f"VCI income_statement returned no data for {normalized}"
            )
        return VietnamFundamentalResult(
            ratios=ratios.copy(),
            income=income.copy(),
            metadata=VietnamFundamentalMetadata(
                package=self.package,
                package_version=self.package_version,
                access_mode=self.access_mode,
                upstream_source=self.source,
                method="quarterly_ratio_and_income_statement",
                symbol=normalized,
            ),
        )


def fundamental_source_label(metadata: VietnamFundamentalMetadata) -> str:
    """Return the stable upstream identity used by fundamental upserts."""
    return metadata.upstream_source.lower()


def fundamental_methodology(metadata: VietnamFundamentalMetadata) -> str:
    package = metadata.package.replace("_", "-")
    return (
        "VCI quarterly RATIO_TTM aligned to day after financial-report "
        f"publicDate; acquired via {package} {metadata.package_version}"
    )
