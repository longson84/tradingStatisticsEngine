"""Provider adapters producing normalized point-in-time fundamental frames."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pandas as pd

from api.providers.vietnam_fundamentals import (
    VietnamFundamentalResult,
    VnstockFundamentalProvider,
    fundamental_methodology,
    fundamental_source_label,
)
from api.providers.vietnam_market import ProviderDataError

IDENTITY_COLUMNS = ["effective_date", "period_end", "period"]
VALUE_COLUMNS = [
    "eps_ttm",
    "book_value_per_share",
    "revenue_ttm",
    "gross_profit_ttm",
    "operating_income_ttm",
    "net_income_ttm",
    "shares_outstanding",
    "equity",
    "total_assets",
    "total_debt",
    "market_cap",
    "roe",
    "roa",
    "debt_to_equity",
    "gross_margin",
    "operating_margin",
    "net_margin",
    "current_ratio",
    "quick_ratio",
    "dividend_yield",
    "reported_pe",
    "reported_pb",
    "reported_ps",
    "reported_ev_ebitda",
]
FUNDAMENTAL_COLUMNS = IDENTITY_COLUMNS + VALUE_COLUMNS


def fetch_provider_fundamentals(
    symbol: str,
    adapter: str,
    *,
    vn_provider: VnstockFundamentalProvider | None = None,
) -> tuple[pd.DataFrame, str, str]:
    """Fetch normalized snapshots without reading or writing local files."""
    normalized = symbol.upper().strip()
    if adapter == "vnstock":
        return _fetch_vn_fundamentals(normalized, provider=vn_provider)
    if adapter != "yfinance":
        raise ValueError(f"Unsupported fundamental adapter: {adapter}")
    frame, method = _fetch_us_fundamentals(normalized)
    return frame, "yfinance", method


def merge_fundamentals(existing: pd.DataFrame, fetched: pd.DataFrame) -> pd.DataFrame:
    """Merge snapshots indefinitely, preferring newer non-null values."""
    frames = [frame for frame in (existing, fetched) if not frame.empty]
    if not frames:
        return empty_fundamentals()
    combined = pd.concat([normalize_fundamentals(frame) for frame in frames], ignore_index=True)
    combined = combined.sort_values(["effective_date", "period_end"], na_position="first")

    def latest_non_null(values: pd.Series):
        non_null = values.dropna()
        return non_null.iloc[-1] if not non_null.empty else pd.NA

    merged = combined.groupby("effective_date", as_index=False, sort=True).agg({
        "period_end": latest_non_null,
        "period": latest_non_null,
        **{column: latest_non_null for column in VALUE_COLUMNS},
    })
    return normalize_fundamentals(merged)


def normalize_fundamentals(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()
    for column in FUNDAMENTAL_COLUMNS:
        if column not in normalized.columns:
            normalized[column] = pd.NA
    normalized["effective_date"] = pd.to_datetime(
        normalized["effective_date"], errors="coerce"
    ).dt.normalize()
    normalized["period_end"] = pd.to_datetime(
        normalized["period_end"], errors="coerce"
    ).dt.normalize()
    for column in VALUE_COLUMNS:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
    return (
        normalized[FUNDAMENTAL_COLUMNS]
        .dropna(subset=["effective_date"])
        .sort_values("effective_date")
        .reset_index(drop=True)
    )


def empty_fundamentals() -> pd.DataFrame:
    return pd.DataFrame(columns=FUNDAMENTAL_COLUMNS)


def _fetch_us_fundamentals(symbol: str) -> tuple[pd.DataFrame, str]:
    import yfinance as yf

    ticker = yf.Ticker(symbol)
    earnings = ticker.get_earnings_dates(limit=100)
    balance = ticker.get_balance_sheet(freq="quarterly", pretty=False)
    income = ticker.get_income_stmt(freq="quarterly", pretty=False)
    eps_rows, report_dates = _yahoo_eps_rows(earnings)
    statement_rows = _yahoo_statement_rows(balance, income, report_dates)
    return (
        merge_fundamentals(eps_rows, statement_rows),
        "Yahoo reported EPS plus quarterly income and balance sheet, effective next day",
    )


def _yahoo_eps_rows(
    earnings: pd.DataFrame | None,
) -> tuple[pd.DataFrame, pd.DatetimeIndex]:
    if earnings is None or earnings.empty or "Reported EPS" not in earnings.columns:
        return empty_fundamentals(), pd.DatetimeIndex([])
    rows = earnings.reset_index()
    date_column = rows.columns[0]
    rows = rows[[date_column, "Reported EPS"]].rename(
        columns={date_column: "reported_at", "Reported EPS": "quarter_eps"}
    )
    rows["reported_at"] = pd.to_datetime(rows["reported_at"], utc=True, errors="coerce")
    rows["quarter_eps"] = pd.to_numeric(rows["quarter_eps"], errors="coerce")
    rows = rows.dropna().sort_values("reported_at").drop_duplicates("reported_at", keep="last")
    rows["eps_ttm"] = rows["quarter_eps"].rolling(4, min_periods=4).sum()
    rows["effective_date"] = (
        rows["reported_at"].dt.tz_convert(None).dt.normalize() + pd.Timedelta(days=1)
    )
    rows["period_end"] = pd.NaT
    rows["period"] = rows["reported_at"].dt.strftime("earnings-%Y-%m-%d")
    result = normalize_fundamentals(rows[["effective_date", "period_end", "period", "eps_ttm"]])
    return result, pd.DatetimeIndex(rows["reported_at"].dt.tz_convert(None).dt.normalize())


def _yahoo_statement_rows(
    balance: pd.DataFrame,
    income: pd.DataFrame,
    report_dates: pd.DatetimeIndex,
) -> pd.DataFrame:
    period_ends = sorted(set(balance.columns) | set(income.columns))
    rows: list[dict[str, Any]] = []
    income_chronological = income.reindex(columns=period_ends)
    rolling = {
        field: _statement_series(income_chronological, [field]).rolling(4, min_periods=4).sum()
        for field in ("TotalRevenue", "GrossProfit", "OperatingIncome", "NetIncome")
    }
    for period_end in period_ends:
        period_timestamp = pd.Timestamp(period_end).normalize()
        candidates = report_dates[
            (report_dates >= period_timestamp) &
            (report_dates <= period_timestamp + pd.Timedelta(days=120))
        ]
        if candidates.empty:
            continue
        effective_date = candidates.min() + pd.Timedelta(days=1)
        equity = _statement_value(
            balance, period_end, ["StockholdersEquity", "CommonStockEquity"]
        )
        shares = _statement_value(
            balance, period_end, ["OrdinarySharesNumber", "ShareIssued"]
        )
        assets = _statement_value(balance, period_end, ["TotalAssets"])
        debt = _statement_value(balance, period_end, ["TotalDebt"])
        revenue = _series_value(rolling["TotalRevenue"], period_end)
        gross_profit = _series_value(rolling["GrossProfit"], period_end)
        operating_income = _series_value(rolling["OperatingIncome"], period_end)
        net_income = _series_value(rolling["NetIncome"], period_end)
        rows.append({
            "effective_date": effective_date,
            "period_end": period_timestamp,
            "period": f"{period_timestamp.year}-Q{period_timestamp.quarter}",
            "book_value_per_share": equity / shares if equity and shares else None,
            "revenue_ttm": revenue,
            "gross_profit_ttm": gross_profit,
            "operating_income_ttm": operating_income,
            "net_income_ttm": net_income,
            "shares_outstanding": shares,
            "equity": equity,
            "total_assets": assets,
            "total_debt": debt,
            "roe": net_income / equity if net_income and equity else None,
            "roa": net_income / assets if net_income and assets else None,
            "debt_to_equity": debt / equity if debt and equity else None,
            "gross_margin": gross_profit / revenue if gross_profit and revenue else None,
            "operating_margin": operating_income / revenue if operating_income and revenue else None,
            "net_margin": net_income / revenue if net_income and revenue else None,
        })
    return normalize_fundamentals(pd.DataFrame(rows)) if rows else empty_fundamentals()


def _statement_series(frame: pd.DataFrame, fields: list[str]) -> pd.Series:
    for field in fields:
        if field in frame.index:
            return pd.to_numeric(frame.loc[field], errors="coerce")
    return pd.Series(index=frame.columns, dtype=float)


def _statement_value(frame: pd.DataFrame, period: Any, fields: list[str]) -> float | None:
    series = _statement_series(frame, fields)
    return _series_value(series, period)


def _series_value(series: pd.Series, period: Any) -> float | None:
    if period not in series.index or pd.isna(series.loc[period]):
        return None
    return float(series.loc[period])


def _fetch_vn_fundamentals(
    symbol: str,
    *,
    provider: VnstockFundamentalProvider | None = None,
) -> tuple[pd.DataFrame, str, str]:
    result = (provider or VnstockFundamentalProvider()).fetch(symbol)
    frame = _normalize_vn_quant_ratios(result)
    return (
        frame,
        fundamental_source_label(result.metadata),
        fundamental_methodology(result.metadata),
    )


_QUANT_REQUIRED_IDS = {
    "RT_VALUE_PE",
    "RT_VALUE_PB",
    "RT_VALUE_MARKET_CAP",
    "RT_VALUE_OUTSTANDING_SHARES",
    "RT_VALUE_EPS",
    "RT_VALUE_BVPS",
}
_QUANT_VALUE_IDS = {
    "eps_ttm": "RT_VALUE_EPS",
    "book_value_per_share": "RT_VALUE_BVPS",
    "shares_outstanding": "RT_VALUE_OUTSTANDING_SHARES",
    "equity": "RT_VALUE_EQUITY",
    "market_cap": "RT_VALUE_MARKET_CAP",
    "roe": "RT_PRT_ROE",
    "roa": "RT_PRT_ROA",
    "debt_to_equity": "RT_LEV_LOAN_EQUITY",
    "gross_margin": "RT_PRT_GROSS_MARGIN",
    "operating_margin": "RT_PRT_EBIT_MARGIN",
    "net_margin": "RT_PRT_NET_MARGIN",
    "current_ratio": "RT_LQD_CR",
    "quick_ratio": "RT_LQD_QR",
    "reported_pe": "RT_VALUE_PE",
    "reported_pb": "RT_VALUE_PB",
    "reported_ps": "RT_VALUE_PS",
    "reported_ev_ebitda": "RT_VALUE_EV_EBITDA",
}


def _normalize_vn_quant_ratios(
    result: VietnamFundamentalResult,
) -> pd.DataFrame:
    acquired_at = result.acquired_at
    if not isinstance(acquired_at, datetime):
        raise ProviderDataError("Vnstock acquisition timestamp is missing or invalid")
    acquired_at = (
        acquired_at.replace(tzinfo=UTC)
        if acquired_at.tzinfo is None
        else acquired_at.astimezone(UTC)
    )
    ratios = result.ratios.copy()
    required_columns = {"period", "id", "value"}
    if ratios.empty or not required_columns.issubset(ratios.columns):
        raise ProviderDataError(
            f"No complete quarterly ratio period returned for {result.metadata.symbol}"
        )
    ratios["value"] = pd.to_numeric(ratios["value"], errors="coerce")
    ratios = ratios[
        ratios["period"].astype(str).str.fullmatch(r"\d{4}-Q[1-4]")
    ].dropna(subset=["value"])
    complete_periods = [
        period
        for period, group in ratios.groupby("period")
        if _QUANT_REQUIRED_IDS.issubset(set(group["id"]))
    ]
    if not complete_periods:
        raise ProviderDataError(
            f"No complete quarterly ratio period returned for {result.metadata.symbol}"
        )
    period = max(complete_periods, key=lambda value: pd.Period(value, freq="Q"))
    values = (
        ratios.loc[ratios["period"] == period]
        .drop_duplicates("id", keep="last")
        .set_index("id")["value"]
    )
    row: dict[str, Any] = {
        "effective_date": pd.Timestamp(acquired_at.date()) + pd.Timedelta(days=1),
        "period_end": pd.Period(period, freq="Q").end_time.normalize(),
        "period": period,
    }
    for target, ratio_id in _QUANT_VALUE_IDS.items():
        row[target] = values.get(ratio_id, pd.NA)
    row["net_income_ttm"] = _product(row["eps_ttm"], row["shares_outstanding"])
    row["revenue_ttm"] = _division(row["market_cap"], row["reported_ps"])
    row["gross_profit_ttm"] = _product(row["revenue_ttm"], row["gross_margin"])
    row["operating_income_ttm"] = _product(
        row["revenue_ttm"], row["operating_margin"]
    )
    row["total_debt"] = _product(row["debt_to_equity"], row["equity"])
    return normalize_fundamentals(pd.DataFrame([row]))


def _product(left: object, right: object) -> float | None:
    if pd.isna(left) or pd.isna(right):
        return None
    return float(left) * float(right)


def _division(numerator: object, denominator: object) -> float | None:
    if pd.isna(numerator) or pd.isna(denominator) or float(denominator) == 0:
        return None
    return float(numerator) / float(denominator)
