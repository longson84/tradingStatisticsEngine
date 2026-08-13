"""Normalized contracts for external company-universe providers."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import re
from typing import Literal, Protocol


CountryCode = Literal["US", "VN"]
_US_TICKER = re.compile(r"^[A-Z0-9][A-Z0-9-]{0,31}$")
_VN_TICKER = re.compile(r"^[A-Z0-9][A-Z0-9]{0,31}$")


class UniverseProviderError(RuntimeError):
    """Base error for company-universe provider failures."""


class UniverseProviderUnavailableError(UniverseProviderError):
    """Raised when a provider cannot be reached or loaded."""


class UniverseProviderDataError(UniverseProviderError):
    """Raised when a provider returns malformed or unusable membership data."""


class UnsupportedUniverseError(UniverseProviderError):
    """Raised when an adapter does not support the requested universe."""


@dataclass(frozen=True)
class UniverseCompanyIdentifier:
    namespace: str
    value: str


@dataclass(frozen=True)
class UniverseConstituent:
    canonical_ticker: str
    listing_symbol: str
    company_name: str
    sector: str | None = None
    industry: str | None = None
    exchange: str | None = None
    company_identifiers: tuple[UniverseCompanyIdentifier, ...] = ()


@dataclass(frozen=True)
class UniverseSnapshot:
    code: str
    name: str
    country_code: CountryCode
    description: str
    effective_date: date | None
    fetched_at: datetime
    source: str
    constituents: tuple[UniverseConstituent, ...]


class UniverseProvider(Protocol):
    supported_universes: frozenset[str]

    def fetch(self, universe: str) -> UniverseSnapshot: ...


class UniverseProviderRegistry:
    """Resolve one explicitly owned provider for each configured universe."""

    def __init__(self, providers: tuple[UniverseProvider, ...]) -> None:
        self._providers: dict[str, UniverseProvider] = {}
        for provider in providers:
            for code in provider.supported_universes:
                if code in self._providers:
                    raise ValueError(f"Multiple providers configured for {code}")
                self._providers[code] = provider

    @property
    def supported_universes(self) -> frozenset[str]:
        return frozenset(self._providers)

    def fetch(self, universe: str) -> UniverseSnapshot:
        code = universe.upper().strip()
        provider = self._providers.get(code)
        if provider is None:
            raise UnsupportedUniverseError(
                f"No company-universe provider is configured for {universe!r}"
            )
        return provider.fetch(code)


def normalize_ticker(value: object, country_code: CountryCode) -> str:
    """Normalize a provider symbol to the application's price-loader ticker."""
    ticker = str(value).upper().strip()
    if country_code == "US":
        ticker = ticker.replace(".", "-").replace("/", "-")
        pattern = _US_TICKER
    else:
        pattern = _VN_TICKER
    if not ticker or not pattern.fullmatch(ticker):
        raise UniverseProviderDataError(
            f"Invalid {country_code} universe ticker: {value!r}"
        )
    return ticker


def optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def make_constituent(
    *,
    ticker: object,
    country_code: CountryCode,
    company_name: object = None,
    sector: object = None,
    industry: object = None,
    exchange: object = None,
    company_identifiers: tuple[UniverseCompanyIdentifier, ...] = (),
) -> UniverseConstituent:
    listing_symbol = str(ticker).upper().strip()
    canonical = normalize_ticker(ticker, country_code)
    return UniverseConstituent(
        canonical_ticker=canonical,
        listing_symbol=listing_symbol,
        company_name=optional_text(company_name) or canonical,
        sector=optional_text(sector),
        industry=optional_text(industry),
        exchange=optional_text(exchange),
        company_identifiers=company_identifiers,
    )


def make_identifier(namespace: str, value: object) -> UniverseCompanyIdentifier | None:
    normalized_namespace = str(namespace).lower().strip()
    normalized_value = optional_text(value)
    if not normalized_namespace or normalized_value is None:
        return None
    if normalized_namespace == "sec_cik":
        try:
            normalized_value = str(int(float(normalized_value)))
        except (TypeError, ValueError):
            raise UniverseProviderDataError(
                f"Invalid SEC CIK value: {value!r}"
            ) from None
    return UniverseCompanyIdentifier(normalized_namespace, normalized_value)


def validated_constituents(
    values: list[UniverseConstituent] | tuple[UniverseConstituent, ...],
    *,
    universe: str,
) -> tuple[UniverseConstituent, ...]:
    """Reject empty or duplicate normalized membership from one provider."""
    if not values:
        raise UniverseProviderDataError(
            f"{universe} provider returned no constituents"
        )
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value.canonical_ticker in seen:
            duplicates.add(value.canonical_ticker)
        seen.add(value.canonical_ticker)
    if duplicates:
        raise UniverseProviderDataError(
            f"{universe} provider returned duplicate tickers: "
            f"{sorted(duplicates)}"
        )
    return tuple(sorted(values, key=lambda value: value.canonical_ticker))
