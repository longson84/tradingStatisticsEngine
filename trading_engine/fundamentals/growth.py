"""Growth-focused fundamental analysis built on SEC fundamentals."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from trading_engine.fundamentals.sec_edgar import (
    FundamentalQuarterRow,
    FundamentalResult,
    FundamentalRow,
    analyze_sec_fundamentals,
)


@dataclass
class GrowthMetricSnapshot:
    metric: str
    latest_value: float | None
    latest_yoy_pct: float | None
    cagr_3y_pct: float | None
    cagr_5y_pct: float | None
    cagr_10y_pct: float | None
    latest_margin_pct: float | None


@dataclass
class QuarterlyGrowthSnapshot:
    metric: str
    latest_value: float | None
    latest_yoy_pct: float | None
    previous_yoy_pct: float | None
    average_4q_yoy_pct: float | None
    latest_qoq_pct: float | None
    direction: str | None


@dataclass
class AnnualGrowthRow:
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


@dataclass
class QuarterlyGrowthRow:
    period_end: object
    revenue: float | None
    revenue_yoy_pct: float | None
    revenue_qoq_pct: float | None
    operating_income_yoy_pct: float | None
    net_income_yoy_pct: float | None
    free_cash_flow_yoy_pct: float | None
    eps_yoy_pct: float | None
    operating_margin_pct: float | None
    free_cash_flow_margin_pct: float | None


@dataclass
class GrowthQualitySummary:
    revenue_cagr_5y_pct: float | None
    operating_income_cagr_5y_pct: float | None
    free_cash_flow_cagr_5y_pct: float | None
    eps_cagr_5y_pct: float | None
    latest_operating_margin_pct: float | None
    latest_fcf_margin_pct: float | None
    operating_margin_change_5y_pct: float | None
    fcf_margin_change_5y_pct: float | None
    share_count_change_5y_pct: float | None


@dataclass
class GrowthAnalysisResult:
    symbol: str
    cik: str
    entity_name: str
    requested_current_year: int
    first_year: int | None
    last_year: int | None
    annual_metrics: list[GrowthMetricSnapshot]
    quarterly_metrics: list[QuarterlyGrowthSnapshot]
    annual_rows: list[AnnualGrowthRow]
    quarterly_rows: list[QuarterlyGrowthRow]
    summary: GrowthQualitySummary


def analyze_growth_fundamentals(symbol: str, current_year: int, years: int = 20) -> GrowthAnalysisResult:
    base = analyze_sec_fundamentals(symbol=symbol, current_year=current_year, years=years)
    annual_rows = _annual_growth_rows(base.rows)
    quarterly_rows = _quarterly_growth_rows(base.quarter_rows)

    latest = base.rows[-1] if base.rows else None
    return GrowthAnalysisResult(
        symbol=base.symbol,
        cik=base.cik,
        entity_name=base.entity_name,
        requested_current_year=base.requested_current_year,
        first_year=base.first_year,
        last_year=base.last_year,
        annual_metrics=_annual_metric_snapshots(base.rows),
        quarterly_metrics=_quarter_metric_snapshots(base.quarter_rows),
        annual_rows=annual_rows,
        quarterly_rows=quarterly_rows,
        summary=GrowthQualitySummary(
            revenue_cagr_5y_pct=_cagr_over_years(base.rows, "revenue", 5),
            operating_income_cagr_5y_pct=_cagr_over_years(base.rows, "operating_income", 5),
            free_cash_flow_cagr_5y_pct=_cagr_over_years(base.rows, "free_cash_flow", 5),
            eps_cagr_5y_pct=_cagr_over_years(base.rows, "eps_diluted", 5),
            latest_operating_margin_pct=latest.operating_margin_pct if latest else None,
            latest_fcf_margin_pct=latest.free_cash_flow_margin_pct if latest else None,
            operating_margin_change_5y_pct=_change_over_years(base.rows, "operating_margin_pct", 5),
            fcf_margin_change_5y_pct=_change_over_years(base.rows, "free_cash_flow_margin_pct", 5),
            share_count_change_5y_pct=_pct_change_over_years(base.rows, "diluted_shares", 5),
        ),
    )


def _annual_metric_snapshots(rows: list[FundamentalRow]) -> list[GrowthMetricSnapshot]:
    definitions = [
        ("Revenue", "revenue", "revenue_yoy_pct", None),
        ("Gross Profit", "gross_profit", None, None),
        ("Operating Income", "operating_income", "operating_income_yoy_pct", "operating_margin_pct"),
        ("Net Income", "net_income", "net_income_yoy_pct", None),
        ("Free Cash Flow", "free_cash_flow", "free_cash_flow_yoy_pct", "free_cash_flow_margin_pct"),
        ("Diluted EPS", "eps_diluted", "eps_yoy_pct", None),
    ]
    snapshots: list[GrowthMetricSnapshot] = []
    latest = rows[-1] if rows else None
    for label, value_field, yoy_field, margin_field in definitions:
        snapshots.append(GrowthMetricSnapshot(
            metric=label,
            latest_value=_field(latest, value_field),
            latest_yoy_pct=_latest_yoy(rows, value_field, yoy_field),
            cagr_3y_pct=_cagr_over_years(rows, value_field, 3),
            cagr_5y_pct=_cagr_over_years(rows, value_field, 5),
            cagr_10y_pct=_cagr_over_years(rows, value_field, 10),
            latest_margin_pct=_field(latest, margin_field) if margin_field else None,
        ))
    return snapshots


def _quarter_metric_snapshots(rows: list[FundamentalQuarterRow]) -> list[QuarterlyGrowthSnapshot]:
    definitions = [
        ("Revenue", "revenue", "revenue_yoy_pct", "revenue_qoq_pct"),
        ("Operating Income", "operating_income", "operating_income_yoy_pct", None),
        ("Net Income", "net_income", "net_income_yoy_pct", None),
        ("Free Cash Flow", "free_cash_flow", "free_cash_flow_yoy_pct", None),
        ("Diluted EPS", "eps_diluted", "eps_yoy_pct", None),
    ]
    latest = rows[-1] if rows else None
    previous = rows[-2] if len(rows) >= 2 else None
    snapshots: list[QuarterlyGrowthSnapshot] = []
    for label, value_field, yoy_field, qoq_field in definitions:
        latest_yoy = _field(latest, yoy_field)
        previous_yoy = _field(previous, yoy_field)
        snapshots.append(QuarterlyGrowthSnapshot(
            metric=label,
            latest_value=_field(latest, value_field),
            latest_yoy_pct=latest_yoy,
            previous_yoy_pct=previous_yoy,
            average_4q_yoy_pct=_average(_field(row, yoy_field) for row in rows[-4:]),
            latest_qoq_pct=_field(latest, qoq_field) if qoq_field else None,
            direction=_direction(previous_yoy, latest_yoy),
        ))
    return snapshots


def _annual_growth_rows(rows: list[FundamentalRow]) -> list[AnnualGrowthRow]:
    out: list[AnnualGrowthRow] = []
    prev_gross_profit: float | None = None
    prev_shares: float | None = None
    for row in rows:
        out.append(AnnualGrowthRow(
            fiscal_year=row.fiscal_year,
            revenue=row.revenue,
            revenue_yoy_pct=row.revenue_yoy_pct,
            gross_profit_yoy_pct=_pct_change(prev_gross_profit, row.gross_profit),
            operating_income_yoy_pct=row.operating_income_yoy_pct,
            net_income_yoy_pct=row.net_income_yoy_pct,
            free_cash_flow_yoy_pct=row.free_cash_flow_yoy_pct,
            eps_yoy_pct=row.eps_yoy_pct,
            share_count_yoy_pct=_pct_change(prev_shares, row.diluted_shares),
            operating_margin_pct=row.operating_margin_pct,
            free_cash_flow_margin_pct=row.free_cash_flow_margin_pct,
        ))
        if row.gross_profit is not None:
            prev_gross_profit = row.gross_profit
        if row.diluted_shares is not None:
            prev_shares = row.diluted_shares
    return out


def _quarterly_growth_rows(rows: list[FundamentalQuarterRow]) -> list[QuarterlyGrowthRow]:
    return [
        QuarterlyGrowthRow(
            period_end=row.period_end,
            revenue=row.revenue,
            revenue_yoy_pct=row.revenue_yoy_pct,
            revenue_qoq_pct=row.revenue_qoq_pct,
            operating_income_yoy_pct=row.operating_income_yoy_pct,
            net_income_yoy_pct=row.net_income_yoy_pct,
            free_cash_flow_yoy_pct=row.free_cash_flow_yoy_pct,
            eps_yoy_pct=row.eps_yoy_pct,
            operating_margin_pct=row.operating_margin_pct,
            free_cash_flow_margin_pct=row.free_cash_flow_margin_pct,
        )
        for row in rows
    ]


def _latest_yoy(rows: list[FundamentalRow], value_field: str, yoy_field: str | None) -> float | None:
    latest = rows[-1] if rows else None
    if latest is None:
        return None
    if yoy_field:
        return _field(latest, yoy_field)
    if len(rows) < 2:
        return None
    return _pct_change(_field(rows[-2], value_field), _field(latest, value_field))


def _cagr_over_years(rows: list[FundamentalRow], field: str, years: int) -> float | None:
    if not rows:
        return None
    latest = rows[-1]
    target_year = latest.fiscal_year - years
    start = next((row for row in rows if row.fiscal_year >= target_year and _field(row, field) is not None), None)
    if start is None or start.fiscal_year >= latest.fiscal_year:
        return None
    return _cagr(_field(start, field), _field(latest, field), latest.fiscal_year - start.fiscal_year)


def _change_over_years(rows: list[FundamentalRow], field: str, years: int) -> float | None:
    if not rows:
        return None
    latest = rows[-1]
    target_year = latest.fiscal_year - years
    start = next((row for row in rows if row.fiscal_year >= target_year and _field(row, field) is not None), None)
    if start is None:
        return None
    start_value = _field(start, field)
    latest_value = _field(latest, field)
    if start_value is None or latest_value is None:
        return None
    return latest_value - start_value


def _pct_change_over_years(rows: list[FundamentalRow], field: str, years: int) -> float | None:
    if not rows:
        return None
    latest = rows[-1]
    target_year = latest.fiscal_year - years
    start = next((row for row in rows if row.fiscal_year >= target_year and _field(row, field) is not None), None)
    if start is None:
        return None
    return _pct_change(_field(start, field), _field(latest, field))


def _field(row: object | None, field: str | None) -> float | None:
    if row is None or field is None:
        return None
    value = getattr(row, field, None)
    return float(value) if isinstance(value, (int, float)) else None


def _pct_change(previous: float | None, current: float | None) -> float | None:
    if previous in (None, 0) or current is None:
        return None
    return (current / previous - 1) * 100


def _cagr(first: float | None, last: float | None, periods: int) -> float | None:
    if first is None or last is None or first <= 0 or last <= 0 or periods <= 0:
        return None
    return ((last / first) ** (1 / periods) - 1) * 100


def _average(values: Iterable[float | None]) -> float | None:
    nums = [value for value in values if value is not None]
    return sum(nums) / len(nums) if nums else None


def _direction(previous: float | None, current: float | None) -> str | None:
    if previous is None or current is None:
        return None
    if current > previous:
        return "accelerating"
    if current < previous:
        return "decelerating"
    return "flat"
