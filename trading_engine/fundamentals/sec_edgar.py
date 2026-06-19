"""SEC EDGAR annual fundamental history.

This module uses the official SEC companyfacts endpoint and converts raw XBRL
facts into a compact annual table.  It deliberately keys annual rows by the
actual period end year, not by SEC ``fy``, because 10-K filings can include
comparative facts for prior fiscal years.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import gzip
import json
import os
import urllib.request
from zoneinfo import ZoneInfo


SEC_USER_AGENT = os.environ.get(
    "SEC_USER_AGENT",
    "tradingStatisticsEngine/0.1 research contact@example.com",
)


@dataclass
class FundamentalRow:
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


@dataclass
class FundamentalQuarterRow:
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


@dataclass
class FundamentalSummary:
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


@dataclass
class FundamentalResult:
    symbol: str
    cik: str
    entity_name: str
    requested_current_year: int
    first_year: int | None
    last_year: int | None
    rows: list[FundamentalRow]
    quarter_rows: list[FundamentalQuarterRow]
    summary: FundamentalSummary


def analyze_sec_fundamentals(
    symbol: str,
    current_year: int,
    years: int = 20,
) -> FundamentalResult:
    """Fetch and normalize annual SEC fundamentals for a ticker."""
    if years < 1:
        raise ValueError("years must be at least 1")
    symbol = symbol.upper().strip()
    cik = _ticker_to_cik(symbol)
    companyfacts = _fetch_json(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json")
    filing_metadata = _filing_metadata(cik)
    facts = companyfacts.get("facts", {}).get("us-gaap", {})

    revenue = _duration_facts(facts, [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    ])
    gross_profit = _duration_facts(facts, ["GrossProfit"])
    operating_income = _duration_facts(facts, ["OperatingIncomeLoss"])
    net_income = _duration_facts(facts, ["NetIncomeLoss"])
    operating_cash_flow = _duration_facts(facts, [
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ])
    capex = _duration_facts(facts, ["PaymentsToAcquirePropertyPlantAndEquipment"])
    eps = _duration_facts(facts, ["EarningsPerShareDiluted"], "USD/shares")
    shares = _duration_facts(facts, ["WeightedAverageNumberOfDilutedSharesOutstanding"], "shares")

    quarterly_revenue = _quarter_duration_facts(facts, [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    ])
    quarterly_gross_profit = _quarter_duration_facts(facts, ["GrossProfit"])
    quarterly_operating_income = _quarter_duration_facts(facts, ["OperatingIncomeLoss"])
    quarterly_net_income = _quarter_duration_facts(facts, ["NetIncomeLoss"])
    quarterly_operating_cash_flow = _quarter_duration_facts(facts, [
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ])
    quarterly_capex = _quarter_duration_facts(facts, ["PaymentsToAcquirePropertyPlantAndEquipment"])
    quarterly_eps = _quarter_duration_facts(facts, ["EarningsPerShareDiluted"], "USD/shares", derive_q4=False)
    quarterly_shares = _quarter_duration_facts(facts, ["WeightedAverageNumberOfDilutedSharesOutstanding"], "shares", derive_q4=False)

    cash_sti = _instant_facts(facts, ["CashCashEquivalentsAndShortTermInvestments"])
    cash = _instant_facts(facts, [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ])
    long_term_debt = _instant_facts(facts, ["LongTermDebt"])
    current_debt = _instant_facts(facts, ["LongTermDebtCurrent", "ShortTermBorrowings"])
    equity = _instant_facts(facts, ["StockholdersEquity"])

    quarterly_cash_sti = _quarter_instant_facts(facts, ["CashCashEquivalentsAndShortTermInvestments"])
    quarterly_cash = _quarter_instant_facts(facts, [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ])
    quarterly_long_term_debt = _quarter_instant_facts(facts, ["LongTermDebt"])
    quarterly_current_debt = _quarter_instant_facts(facts, ["LongTermDebtCurrent", "ShortTermBorrowings"])

    start_year = current_year - years
    selected_years = sorted(
        y for y in set(revenue) | set(net_income)
        if start_year <= y <= current_year
    )

    rows: list[FundamentalRow] = []
    previous_revenue: float | None = None
    previous_operating_income: float | None = None
    previous_net_income: float | None = None
    previous_free_cash_flow: float | None = None
    previous_eps: float | None = None
    for fy in selected_years:
        rev = _value(revenue, fy)
        op_income = _value(operating_income, fy)
        ni = _value(net_income, fy)
        cfo = _value(operating_cash_flow, fy)
        cx = _value(capex, fy)
        fcf = cfo - cx if cfo is not None and cx is not None else None
        liquidity = _value(cash_sti, fy)
        if liquidity is None:
            liquidity = _value(cash, fy)
        debt = (_value(long_term_debt, fy) or 0.0) + (_value(current_debt, fy) or 0.0)
        debt = debt or None
        filed = _filed_date(revenue.get(fy) or net_income.get(fy))
        annual_period_end = _period_end(revenue.get(fy) or net_income.get(fy))
        accepted_at = _accepted_at(filing_metadata, "10-K", filed, annual_period_end)

        rows.append(FundamentalRow(
            fiscal_year=fy,
            filed=filed,
            filing_accepted_at=accepted_at,
            filing_timing=_filing_timing(accepted_at),
            reaction_session_date=None,
            filing_return_pct=None,
            revenue=rev,
            revenue_yoy_pct=_pct_change(previous_revenue, rev),
            gross_profit=_value(gross_profit, fy),
            operating_income=op_income,
            operating_income_yoy_pct=_pct_change(previous_operating_income, op_income),
            operating_margin_pct=_ratio_pct(op_income, rev),
            net_income=ni,
            net_income_yoy_pct=_pct_change(previous_net_income, ni),
            free_cash_flow=fcf,
            free_cash_flow_yoy_pct=_pct_change(previous_free_cash_flow, fcf),
            free_cash_flow_margin_pct=_ratio_pct(fcf, rev),
            capex=cx,
            capex_to_revenue_pct=_ratio_pct(cx, rev),
            cash_and_short_term_investments=liquidity,
            debt=debt,
            net_cash=liquidity - debt if liquidity is not None and debt is not None else None,
            debt_to_fcf=debt / fcf if debt is not None and fcf and fcf > 0 else None,
            equity=_value(equity, fy),
            eps_diluted=_value(eps, fy),
            eps_yoy_pct=_pct_change(previous_eps, _value(eps, fy)),
            diluted_shares=_value(shares, fy),
        ))
        if rev is not None:
            previous_revenue = rev
        if op_income is not None:
            previous_operating_income = op_income
        if ni is not None:
            previous_net_income = ni
        if fcf is not None:
            previous_free_cash_flow = fcf
        if _value(eps, fy) is not None:
            previous_eps = _value(eps, fy)

    quarter_cutoff_year = current_year
    all_quarter_dates = sorted(
        d for d in set(quarterly_revenue) | set(quarterly_net_income)
        if d.year <= quarter_cutoff_year
    )
    selected_quarter_dates = all_quarter_dates[-20:]

    quarter_rows: list[FundamentalQuarterRow] = []
    for index, period_end in enumerate(selected_quarter_dates):
        rev = _period_value(quarterly_revenue, period_end)
        op_income = _period_value(quarterly_operating_income, period_end)
        ni = _period_value(quarterly_net_income, period_end)
        cfo = _period_value(quarterly_operating_cash_flow, period_end)
        cx = _period_value(quarterly_capex, period_end)
        fcf = cfo - cx if cfo is not None and cx is not None else None
        liquidity = _period_value(quarterly_cash_sti, period_end)
        if liquidity is None:
            liquidity = _period_value(quarterly_cash, period_end)
        debt = (_period_value(quarterly_long_term_debt, period_end) or 0.0) + (_period_value(quarterly_current_debt, period_end) or 0.0)
        debt = debt or None
        same_quarter_last_year = quarter_rows[index - 4] if index >= 4 else None
        previous_quarter = quarter_rows[index - 1] if index >= 1 else None
        filed = _filed_date(quarterly_revenue.get(period_end) or quarterly_net_income.get(period_end))
        accepted_at = _accepted_at(filing_metadata, "10-Q", filed, period_end)

        quarter_rows.append(FundamentalQuarterRow(
            period_end=period_end,
            filed=filed,
            filing_accepted_at=accepted_at,
            filing_timing=_filing_timing(accepted_at),
            reaction_session_date=None,
            filing_return_pct=None,
            revenue=rev,
            revenue_yoy_pct=_pct_change(same_quarter_last_year.revenue if same_quarter_last_year else None, rev),
            revenue_qoq_pct=_pct_change(previous_quarter.revenue if previous_quarter else None, rev),
            operating_income=op_income,
            operating_income_yoy_pct=_pct_change(same_quarter_last_year.operating_income if same_quarter_last_year else None, op_income),
            operating_margin_pct=_ratio_pct(op_income, rev),
            net_income=ni,
            net_income_yoy_pct=_pct_change(same_quarter_last_year.net_income if same_quarter_last_year else None, ni),
            free_cash_flow=fcf,
            free_cash_flow_yoy_pct=_pct_change(same_quarter_last_year.free_cash_flow if same_quarter_last_year else None, fcf),
            free_cash_flow_margin_pct=_ratio_pct(fcf, rev),
            capex=cx,
            capex_to_revenue_pct=_ratio_pct(cx, rev),
            cash_and_short_term_investments=liquidity,
            debt=debt,
            net_cash=liquidity - debt if liquidity is not None and debt is not None else None,
            eps_diluted=_period_value(quarterly_eps, period_end),
            eps_yoy_pct=_pct_change(same_quarter_last_year.eps_diluted if same_quarter_last_year else None, _period_value(quarterly_eps, period_end)),
            diluted_shares=_period_value(quarterly_shares, period_end),
        ))

    return FundamentalResult(
        symbol=symbol,
        cik=cik,
        entity_name=str(companyfacts.get("entityName", symbol)),
        requested_current_year=current_year,
        first_year=rows[0].fiscal_year if rows else None,
        last_year=rows[-1].fiscal_year if rows else None,
        rows=rows,
        quarter_rows=quarter_rows,
        summary=_build_summary(rows),
    )


def _ticker_to_cik(symbol: str) -> str:
    tickers = _fetch_json("https://www.sec.gov/files/company_tickers.json")
    for item in tickers.values():
        if str(item.get("ticker", "")).upper() == symbol:
            return str(item["cik_str"]).zfill(10)
    raise ValueError(f"No SEC CIK found for ticker {symbol!r}")


def _fetch_json(url: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": SEC_USER_AGENT,
            "Accept-Encoding": "gzip",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read()
        if response.headers.get("Content-Encoding") == "gzip" or raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
    return json.loads(raw)


def _filing_metadata(cik: str) -> dict[tuple[str, date | None, date | None], datetime]:
    submissions = _fetch_json(f"https://data.sec.gov/submissions/CIK{cik}.json")
    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    filing_dates = recent.get("filingDate", [])
    report_dates = recent.get("reportDate", [])
    accepted_times = recent.get("acceptanceDateTime", [])
    out: dict[tuple[str, date | None, date | None], datetime] = {}
    for form, filing_date, report_date, accepted_time in zip(forms, filing_dates, report_dates, accepted_times):
        if form not in {"10-K", "10-Q"} or not accepted_time:
            continue
        filed = _parse_date(filing_date)
        period_end = _parse_date(report_date)
        accepted_at = _parse_datetime(accepted_time)
        if accepted_at is not None:
            out[(form, filed, period_end)] = accepted_at
    return out


def _accepted_at(
    filing_metadata: dict[tuple[str, date | None, date | None], datetime],
    form: str,
    filed: date | None,
    period_end: date | None,
) -> datetime | None:
    return filing_metadata.get((form, filed, period_end))


def _filing_timing(accepted_at: datetime | None) -> str | None:
    if accepted_at is None:
        return None
    accepted_et = accepted_at.astimezone(ZoneInfo("America/New_York"))
    session_minutes = accepted_et.hour * 60 + accepted_et.minute
    if session_minutes < 9 * 60 + 30:
        return "before_open"
    if session_minutes >= 16 * 60:
        return "after_close"
    return "market_hours"


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _duration_facts(facts: dict, concepts: list[str], unit: str = "USD") -> dict[int, dict]:
    out: dict[int, dict] = {}
    for concept in concepts:
        for fact in facts.get(concept, {}).get("units", {}).get(unit, []):
            if fact.get("form") != "10-K" or "val" not in fact:
                continue
            start = fact.get("start")
            end = fact.get("end")
            if not start or not end:
                continue
            try:
                days = (date.fromisoformat(end) - date.fromisoformat(start)).days
            except ValueError:
                continue
            if days < 300 or days > 380:
                continue
            fiscal_year = int(end[:4])
            old = out.get(fiscal_year)
            if old is None or str(fact.get("filed", "9999")) < str(old.get("filed", "9999")):
                out[fiscal_year] = {**fact, "concept": concept}
    return out


def _quarter_duration_facts(
    facts: dict,
    concepts: list[str],
    unit: str = "USD",
    derive_q4: bool = True,
) -> dict[date, dict]:
    out: dict[date, dict] = {}
    for concept in concepts:
        for fact in facts.get(concept, {}).get("units", {}).get(unit, []):
            if fact.get("form") != "10-Q" or "val" not in fact:
                continue
            start = fact.get("start")
            end = fact.get("end")
            if not start or not end:
                continue
            try:
                start_date = date.fromisoformat(start)
                end_date = date.fromisoformat(end)
            except ValueError:
                continue
            days = (end_date - start_date).days
            if days < 70 or days > 105:
                continue
            old = out.get(end_date)
            if old is None or str(fact.get("filed", "9999")) < str(old.get("filed", "9999")):
                out[end_date] = {
                    **fact,
                    "concept": concept,
                    "_start_date": start_date,
                    "_end_date": end_date,
                }
    if derive_q4:
        _add_derived_q4_facts(out, _annual_duration_period_facts(facts, concepts, unit))
    return out


def _annual_duration_period_facts(facts: dict, concepts: list[str], unit: str = "USD") -> dict[date, dict]:
    out: dict[date, dict] = {}
    for concept in concepts:
        for fact in facts.get(concept, {}).get("units", {}).get(unit, []):
            if fact.get("form") != "10-K" or "val" not in fact:
                continue
            start = fact.get("start")
            end = fact.get("end")
            if not start or not end:
                continue
            try:
                start_date = date.fromisoformat(start)
                end_date = date.fromisoformat(end)
            except ValueError:
                continue
            days = (end_date - start_date).days
            if days < 300 or days > 380:
                continue
            old = out.get(end_date)
            if old is None or str(fact.get("filed", "9999")) < str(old.get("filed", "9999")):
                out[end_date] = {
                    **fact,
                    "concept": concept,
                    "_start_date": start_date,
                    "_end_date": end_date,
                }
    return out


def _add_derived_q4_facts(quarters: dict[date, dict], annuals: dict[date, dict]) -> None:
    for period_end, annual in annuals.items():
        if period_end in quarters:
            continue
        start_date = annual["_start_date"]
        first_three_quarters = [
            fact for fact in quarters.values()
            if start_date <= fact["_start_date"] and fact["_end_date"] < period_end
        ]
        by_end_date = {fact["_end_date"]: fact for fact in first_three_quarters}
        if len(by_end_date) != 3:
            continue
        derived_value = float(annual["val"]) - sum(float(fact["val"]) for fact in by_end_date.values())
        quarters[period_end] = {
            **annual,
            "form": "10-K-derived",
            "val": derived_value,
            "_start_date": max(fact["_end_date"] for fact in by_end_date.values()),
            "_end_date": period_end,
        }


def _instant_facts(facts: dict, concepts: list[str], unit: str = "USD") -> dict[int, dict]:
    out: dict[int, dict] = {}
    for concept in concepts:
        for fact in facts.get(concept, {}).get("units", {}).get(unit, []):
            if fact.get("form") != "10-K" or "val" not in fact or not fact.get("end"):
                continue
            fiscal_year = int(str(fact["end"])[:4])
            old = out.get(fiscal_year)
            if old is None or str(fact.get("filed", "9999")) < str(old.get("filed", "9999")):
                out[fiscal_year] = {**fact, "concept": concept}
    return out


def _quarter_instant_facts(facts: dict, concepts: list[str], unit: str = "USD") -> dict[date, dict]:
    out: dict[date, dict] = {}
    for concept in concepts:
        for fact in facts.get(concept, {}).get("units", {}).get(unit, []):
            if fact.get("form") not in {"10-Q", "10-K"} or "val" not in fact or not fact.get("end"):
                continue
            try:
                period_end = date.fromisoformat(str(fact["end"]))
            except ValueError:
                continue
            old = out.get(period_end)
            if old is None or str(fact.get("filed", "9999")) < str(old.get("filed", "9999")):
                out[period_end] = {**fact, "concept": concept, "_end_date": period_end}
    return out


def _value(facts_by_year: dict[int, dict], fiscal_year: int) -> float | None:
    value = facts_by_year.get(fiscal_year, {}).get("val")
    return float(value) if value is not None else None


def _period_value(facts_by_period: dict[date, dict], period_end: date) -> float | None:
    value = facts_by_period.get(period_end, {}).get("val")
    return float(value) if value is not None else None


def _filed_date(fact: dict | None) -> date | None:
    if not fact or not fact.get("filed"):
        return None
    return date.fromisoformat(str(fact["filed"]))


def _period_end(fact: dict | None) -> date | None:
    if not fact or not fact.get("end"):
        return None
    return date.fromisoformat(str(fact["end"]))


def _ratio_pct(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator * 100


def _pct_change(previous: float | None, current: float | None) -> float | None:
    if previous in (None, 0) or current is None:
        return None
    return (current / previous - 1) * 100


def _cagr(first: float | None, last: float | None, periods: int) -> float | None:
    if first is None or last is None or first <= 0 or last <= 0 or periods <= 0:
        return None
    return ((last / first) ** (1 / periods) - 1) * 100


def _build_summary(rows: list[FundamentalRow]) -> FundamentalSummary:
    first = rows[0] if rows else None
    last = rows[-1] if rows else None
    periods = (last.fiscal_year - first.fiscal_year) if first and last else 0
    return FundamentalSummary(
        revenue_cagr_pct=_cagr(first.revenue if first else None, last.revenue if last else None, periods),
        operating_income_cagr_pct=_cagr(first.operating_income if first else None, last.operating_income if last else None, periods),
        net_income_cagr_pct=_cagr(first.net_income if first else None, last.net_income if last else None, periods),
        free_cash_flow_cagr_pct=_cagr(first.free_cash_flow if first else None, last.free_cash_flow if last else None, periods),
        eps_cagr_pct=_cagr(first.eps_diluted if first else None, last.eps_diluted if last else None, periods),
        latest_operating_margin_pct=last.operating_margin_pct if last else None,
        latest_fcf_margin_pct=last.free_cash_flow_margin_pct if last else None,
        latest_capex_to_revenue_pct=last.capex_to_revenue_pct if last else None,
        latest_debt_to_fcf=last.debt_to_fcf if last else None,
        latest_net_cash=last.net_cash if last else None,
        share_count_change_pct=_pct_change(first.diluted_shares if first else None, last.diluted_shares if last else None),
    )
