"""Provider adapters producing normalized point-in-time fundamental frames."""
from __future__ import annotations

import re
from typing import Any

import pandas as pd

from api.providers.vietnam_fundamentals import (
    VnstockDataFundamentalProvider,
    fundamental_methodology,
    fundamental_source_label,
)

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
    vn_provider: VnstockDataFundamentalProvider | None = None,
) -> tuple[pd.DataFrame, str, str]:
    """Fetch normalized snapshots without reading or writing local files."""
    normalized = symbol.upper().strip()
    if adapter == "vnstock_data":
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
    provider: VnstockDataFundamentalProvider | None = None,
) -> tuple[pd.DataFrame, str, str]:
    result = (provider or VnstockDataFundamentalProvider()).fetch(symbol)
    frame = _normalize_vn_fundamental_reports(result.ratios, result.income)
    return (
        frame,
        fundamental_source_label(result.metadata),
        fundamental_methodology(result.metadata),
    )


def _normalize_vn_fundamental_reports(
    ratios: pd.DataFrame,
    income: pd.DataFrame,
) -> pd.DataFrame:
    ratios = _canonicalize_columns(ratios)
    income = _canonicalize_columns(income)
    required = {"pe", "pb", "marketcap", "numberofsharesmktcap"}
    if ratios.empty or not required.issubset(ratios.columns):
        return empty_fundamentals()

    publications = _vn_publications(income)
    ratios = _vn_quarterly_ratios(ratios, publications)
    if ratios.empty or publications.empty:
        return empty_fundamentals()
    publication_column = next(
        (column for column in ("publicdate", "updatedate", "createdate") if column in income.columns),
        None,
    )
    if publication_column is None:
        return empty_fundamentals()
    rows = ratios.merge(publications, on=["year", "quarter"], how="left")
    shares = _numeric_column(rows, "numberofsharesmktcap")
    market_cap = _numeric_column(rows, "marketcap")
    reported_pe = _numeric_column(rows, "pe")
    reported_pb = _numeric_column(rows, "pb")
    reported_ps = _numeric_column(rows, "ps")
    price_per_share = market_cap / shares
    rows["effective_date"] = (
        pd.to_datetime(rows["published_at"], errors="coerce").dt.normalize()
        + pd.Timedelta(days=1)
    )
    rows["period_end"] = rows.apply(
        lambda row: pd.Period(
            year=int(row["year"]), quarter=int(row["quarter"]), freq="Q"
        ).end_time.normalize(),
        axis=1,
    )
    rows["period"] = rows["year"].astype(str) + "-Q" + rows["quarter"].astype(str)
    rows["eps_ttm"] = price_per_share / reported_pe
    rows["book_value_per_share"] = price_per_share / reported_pb
    rows["revenue_ttm"] = market_cap / reported_ps
    rows["net_income_ttm"] = market_cap / reported_pe
    rows["shares_outstanding"] = shares
    rows["market_cap"] = market_cap
    rows["equity"] = rows["book_value_per_share"] * shares
    mappings = {
        "roe": "roe",
        "roa": "roa",
        "debt_to_equity": "debtperequity",
        "gross_margin": "grossmargin",
        "operating_margin": "ebitmargin",
        "net_margin": "aftertaxprofitmargin",
        "current_ratio": "currentratio",
        "quick_ratio": "quickratio",
        "dividend_yield": "dividendyield",
        "reported_pe": "pe",
        "reported_pb": "pb",
        "reported_ps": "ps",
        "reported_ev_ebitda": "evtoebitda",
    }
    for target, source in mappings.items():
        rows[target] = _numeric_column(rows, source)
    return normalize_fundamentals(rows)


def _canonicalize_columns(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result.columns = [
        re.sub(r"[^a-z0-9]", "", str(column).lower())
        for column in result.columns
    ]
    return result


def _vn_publications(income: pd.DataFrame) -> pd.DataFrame:
    year_column = "yearreport" if "yearreport" in income else "year"
    quarter_column = "lengthreport" if "lengthreport" in income else "quarter"
    publication_column = next(
        (column for column in ("publicdate", "updatedate", "createdate") if column in income),
        None,
    )
    if publication_column is None or year_column not in income or quarter_column not in income:
        return pd.DataFrame(columns=["year", "quarter", "published_at"])
    result = income[[year_column, quarter_column, publication_column]].rename(
        columns={
            year_column: "year",
            quarter_column: "quarter",
            publication_column: "published_at",
        }
    )
    for key in ("year", "quarter"):
        result[key] = pd.to_numeric(result[key], errors="coerce").astype("Int64")
    return (
        result.dropna(subset=["year", "quarter", "published_at"])
        .sort_values(["year", "quarter"])
        .drop_duplicates(["year", "quarter"], keep="last")
        .reset_index(drop=True)
    )


def _vn_quarterly_ratios(
    ratios: pd.DataFrame,
    publications: pd.DataFrame,
) -> pd.DataFrame:
    result = ratios.copy()
    if "ratiotype" in result and result["ratiotype"].notna().any():
        result = result[
            result["ratiotype"].astype(str).str.upper() == "RATIO_TTM"
        ].copy()
    elif "ratioyearid" in result:
        result = result[result["ratioyearid"].isna()].copy()

    year_column = "year" if "year" in result else "yearreport"
    if year_column not in result:
        return result.iloc[0:0]
    result["year"] = pd.to_numeric(result[year_column], errors="coerce").astype("Int64")
    if "quarter" in result:
        result["quarter"] = pd.to_numeric(
            result["quarter"], errors="coerce"
        ).astype("Int64")
        return result.dropna(subset=["year", "quarter"])

    # Sponsored VCI omits the quarter field from its public ratio result while
    # retaining rows in chronological order. Align each year's ratio rows to
    # the latest N published quarters for that same year. This handles partial
    # first years without inventing an unavailable quarter.
    parts: list[pd.DataFrame] = []
    for year, group in result.dropna(subset=["year"]).groupby("year", sort=True):
        available = publications.loc[
            publications["year"] == year, "quarter"
        ].dropna().sort_values()
        if len(group) > len(available):
            continue
        aligned = group.copy()
        aligned["quarter"] = available.iloc[-len(group):].to_numpy()
        parts.append(aligned)
    if not parts:
        return result.iloc[0:0]
    return pd.concat(parts, ignore_index=True)


def _numeric_column(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(float("nan"), index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce")
