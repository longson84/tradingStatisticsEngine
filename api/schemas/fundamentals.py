"""Request/response schemas for fundamental analysis endpoints."""
from __future__ import annotations

from datetime import date, datetime

from typing import Literal

from pydantic import BaseModel, Field


class FundamentalRequest(BaseModel):
    symbol: str
    current_year: int = Field(ge=1990, le=2100)
    years: int = Field(default=20, ge=1, le=40)
    data_source: Literal["yfinance", "vnstock"] = "yfinance"


class FundamentalRowSchema(BaseModel):
    fiscal_year: int
    filed: date | None
    filing_accepted_at: datetime | None
    filing_timing: str | None
    reaction_session_date: date | None
    filing_return_pct: float | None
    revenue: float | None
    revenue_yoy_pct: float | None
    gross_profit: float | None
    operating_income: float | None
    operating_income_yoy_pct: float | None
    operating_margin_pct: float | None
    net_income: float | None
    net_income_yoy_pct: float | None
    free_cash_flow: float | None
    free_cash_flow_yoy_pct: float | None
    free_cash_flow_margin_pct: float | None
    capex: float | None
    capex_to_revenue_pct: float | None
    cash_and_short_term_investments: float | None
    debt: float | None
    net_cash: float | None
    debt_to_fcf: float | None
    equity: float | None
    eps_diluted: float | None
    eps_yoy_pct: float | None
    diluted_shares: float | None


class FundamentalQuarterRowSchema(BaseModel):
    period_end: date
    filed: date | None
    filing_accepted_at: datetime | None
    filing_timing: str | None
    reaction_session_date: date | None
    filing_return_pct: float | None
    revenue: float | None
    revenue_yoy_pct: float | None
    revenue_qoq_pct: float | None
    operating_income: float | None
    operating_income_yoy_pct: float | None
    operating_margin_pct: float | None
    net_income: float | None
    net_income_yoy_pct: float | None
    free_cash_flow: float | None
    free_cash_flow_yoy_pct: float | None
    free_cash_flow_margin_pct: float | None
    capex: float | None
    capex_to_revenue_pct: float | None
    cash_and_short_term_investments: float | None
    debt: float | None
    net_cash: float | None
    eps_diluted: float | None
    eps_yoy_pct: float | None
    diluted_shares: float | None


class FundamentalSummarySchema(BaseModel):
    revenue_cagr_pct: float | None
    operating_income_cagr_pct: float | None
    net_income_cagr_pct: float | None
    free_cash_flow_cagr_pct: float | None
    eps_cagr_pct: float | None
    latest_operating_margin_pct: float | None
    latest_fcf_margin_pct: float | None
    latest_capex_to_revenue_pct: float | None
    latest_debt_to_fcf: float | None
    latest_net_cash: float | None
    share_count_change_pct: float | None


class FundamentalResponse(BaseModel):
    symbol: str
    cik: str
    entity_name: str
    requested_current_year: int
    first_year: int | None
    last_year: int | None
    rows: list[FundamentalRowSchema]
    quarter_rows: list[FundamentalQuarterRowSchema]
    summary: FundamentalSummarySchema


class GrowthMetricSnapshotSchema(BaseModel):
    metric: str
    latest_value: float | None
    latest_yoy_pct: float | None
    cagr_3y_pct: float | None
    cagr_5y_pct: float | None
    cagr_10y_pct: float | None
    latest_margin_pct: float | None


class QuarterlyGrowthSnapshotSchema(BaseModel):
    metric: str
    latest_value: float | None
    latest_yoy_pct: float | None
    previous_yoy_pct: float | None
    average_4q_yoy_pct: float | None
    latest_qoq_pct: float | None
    direction: str | None


class AnnualGrowthRowSchema(BaseModel):
    fiscal_year: int
    revenue: float | None
    revenue_yoy_pct: float | None
    gross_profit_yoy_pct: float | None
    operating_income_yoy_pct: float | None
    net_income_yoy_pct: float | None
    free_cash_flow_yoy_pct: float | None
    eps_yoy_pct: float | None
    share_count_yoy_pct: float | None
    operating_margin_pct: float | None
    free_cash_flow_margin_pct: float | None


class QuarterlyGrowthRowSchema(BaseModel):
    period_end: date
    revenue: float | None
    revenue_yoy_pct: float | None
    revenue_qoq_pct: float | None
    operating_income_yoy_pct: float | None
    net_income_yoy_pct: float | None
    free_cash_flow_yoy_pct: float | None
    eps_yoy_pct: float | None
    operating_margin_pct: float | None
    free_cash_flow_margin_pct: float | None


class GrowthQualitySummarySchema(BaseModel):
    revenue_cagr_5y_pct: float | None
    operating_income_cagr_5y_pct: float | None
    free_cash_flow_cagr_5y_pct: float | None
    eps_cagr_5y_pct: float | None
    latest_operating_margin_pct: float | None
    latest_fcf_margin_pct: float | None
    operating_margin_change_5y_pct: float | None
    fcf_margin_change_5y_pct: float | None
    share_count_change_5y_pct: float | None


class GrowthAnalysisResponse(BaseModel):
    symbol: str
    cik: str
    entity_name: str
    requested_current_year: int
    first_year: int | None
    last_year: int | None
    annual_metrics: list[GrowthMetricSnapshotSchema]
    quarterly_metrics: list[QuarterlyGrowthSnapshotSchema]
    annual_rows: list[AnnualGrowthRowSchema]
    quarterly_rows: list[QuarterlyGrowthRowSchema]
    summary: GrowthQualitySummarySchema


class GrowthAssessmentRequest(BaseModel):
    growth: GrowthAnalysisResponse


class GrowthAssessmentResponse(BaseModel):
    provider: str
    model: str
    good_things: list[str]
    bad_things: list[str]
    risks: list[str]
    opportunities: list[str]
    investment_considerations: list[str]
    disclaimer: str
    prompt: str
