"""Public contracts for canonical instrument discovery."""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


InstrumentScope = Literal["equity", "crypto_spot", "reference_rate"]


class InstrumentCatalogItemResponse(BaseModel):
    id: int
    symbol: str
    instrument_type: str
    company_id: int | None = None
    company_name: str | None = None
    sector: str | None = None
    industry: str | None = None
    venue_code: str | None = None
    venue_name: str | None = None
    base_asset: str | None = None
    quote_asset: str | None = None
    currency: str
    price_basis: str
    price_source: str | None = None
    first_session: date | None = None
    last_session: date | None = None
    stored_sessions: int
    universes: list[str]


class InstrumentFacetCountResponse(BaseModel):
    value: str
    count: int


class InstrumentCatalogFacetsResponse(BaseModel):
    all_count: int
    sectors: list[InstrumentFacetCountResponse]


class InstrumentCatalogResponse(BaseModel):
    total: int
    offset: int
    limit: int
    instruments: list[InstrumentCatalogItemResponse]
    facets: InstrumentCatalogFacetsResponse


class InstrumentPricePointResponse(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None
    eps_ttm: float | None = None
    shares_outstanding: float | None = None
    trailing_pe: float | None = None
    trailing_pb: float | None = None
    relative_strength: float | None = None


class InstrumentPriceHistoryResponse(BaseModel):
    instrument_id: int
    symbol: str
    venue_code: str | None = None
    currency: str
    source: str
    price_basis: str
    fetched_at: str
    first_date: str
    last_date: str
    expected_last_session: date
    is_stale: bool
    row_count: int
    relative_strength_benchmark: Literal["VN30", "SPX"]
    trailing_pe_source: str | None = None
    trailing_pe_method: str | None = None
    trailing_pe_fetched_at: str | None = None
    fundamentals_fields: list[str] = Field(default_factory=list)
    provider_reported_pe: float | None = None
    provider_reported_pb: float | None = None
    provider_ratio_effective_date: str | None = None
    provider_ratio_period: str | None = None
    shares_growth_pct: float | None = None
    shares_growth_cagr_pct: float | None = None
    shares_growth_observed_years: float | None = None
    shares_growth_start_date: str | None = None
    shares_growth_full_10y: bool = False
    shares_cagr_5y_pct: float | None = None
    shares_cagr_5y_observed_years: float | None = None
    shares_cagr_5y_start_date: str | None = None
    shares_cagr_full_5y: bool = False
    prices: list[InstrumentPricePointResponse]
