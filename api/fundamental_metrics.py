"""Canonical mappings between provider frames and normalized fundamentals."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import re


@dataclass(frozen=True)
class MetricSpec:
    metric_code: str
    unit: str
    period_basis: str
    fact_kind: str


FACT_SPECS = {
    "eps_ttm": MetricSpec("eps_ttm", "per_share", "ttm", "provider_derived"),
    "book_value_per_share": MetricSpec(
        "book_value_per_share", "per_share", "instant", "provider_derived"
    ),
    "revenue_ttm": MetricSpec("revenue_ttm", "currency", "ttm", "provider_derived"),
    "gross_profit_ttm": MetricSpec(
        "gross_profit_ttm", "currency", "ttm", "provider_derived"
    ),
    "operating_income_ttm": MetricSpec(
        "operating_income_ttm", "currency", "ttm", "provider_derived"
    ),
    "net_income_ttm": MetricSpec(
        "net_income_ttm", "currency", "ttm", "provider_derived"
    ),
    "shares_outstanding": MetricSpec(
        "shares_outstanding", "shares", "instant", "reported"
    ),
    "equity": MetricSpec("total_equity", "currency", "instant", "reported"),
    "total_assets": MetricSpec("total_assets", "currency", "instant", "reported"),
    "total_debt": MetricSpec("total_debt", "currency", "instant", "reported"),
    "roe": MetricSpec("roe", "ratio", "ttm", "provider_derived"),
    "roa": MetricSpec("roa", "ratio", "ttm", "provider_derived"),
    "debt_to_equity": MetricSpec(
        "debt_to_equity", "ratio", "instant", "provider_derived"
    ),
    "gross_margin": MetricSpec("gross_margin", "ratio", "ttm", "provider_derived"),
    "operating_margin": MetricSpec(
        "operating_margin", "ratio", "ttm", "provider_derived"
    ),
    "net_margin": MetricSpec("net_margin", "ratio", "ttm", "provider_derived"),
    "current_ratio": MetricSpec(
        "current_ratio", "ratio", "instant", "provider_derived"
    ),
    "quick_ratio": MetricSpec("quick_ratio", "ratio", "instant", "provider_derived"),
}

VALUATION_SPECS = {
    "market_cap": ("market_cap", "currency"),
    "dividend_yield": ("dividend_yield", "ratio"),
    "reported_pe": ("pe", "ratio"),
    "reported_pb": ("pb", "ratio"),
    "reported_ps": ("ps", "ratio"),
    "reported_ev_ebitda": ("ev_ebitda", "ratio"),
}


def snapshot_key(
    effective_date: date, period_end: date | None, period: str
) -> str:
    """Return the stable key used by both legacy imports and live refreshes."""
    return f"legacy:{effective_date}:{period_end or '-'}:{period or '-'}"


def period_identity(
    period: str, period_end: date | None
) -> tuple[int | None, int | None, str]:
    quarterly = re.fullmatch(r"(\d{4})-Q([1-4])", period)
    if quarterly:
        return int(quarterly.group(1)), int(quarterly.group(2)), "quarterly"
    if period.startswith("earnings-"):
        year = period_end.year if period_end else None
        return year, None, "earnings"
    annual = re.fullmatch(r"(\d{4})(?:-FY)?", period)
    if annual:
        return int(annual.group(1)), None, "annual"
    if period_end:
        return period_end.year, None, "other"
    return None, None, "other"
