"""Provider adapters producing normalized point-in-time fundamental frames."""
from __future__ import annotations

from typing import Any, Literal

import pandas as pd

FundamentalMarket = Literal["US", "VN"]
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
    symbol: str, market: FundamentalMarket
) -> tuple[pd.DataFrame, str, str]:
    """Fetch normalized snapshots without reading or writing local files."""
    normalized = symbol.upper().strip()
    if market == "VN":
        frame, method = _fetch_vn_fundamentals(normalized)
        return frame, "vnstock-vci-4.0.5", method
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


def _fetch_vn_fundamentals(symbol: str) -> tuple[pd.DataFrame, str]:
    from vnstock import Finance

    finance = Finance(
        source="VCI", symbol=symbol, period="quarter", get_all=True, show_log=False
    )
    provider = finance.provider
    ratios = provider._get_report(
        report_type="ratio", period="quarter", mode="raw", limit=100
    )
    income = provider._get_report(
        report_type="income_statement", period="quarter", mode="raw", limit=100
    )
    required = {"year", "quarter", "ratioType", "pe", "pb", "marketCap", "numberOfSharesMktCap"}
    if ratios.empty or not required.issubset(ratios.columns):
        return empty_fundamentals(), "VCI quarterly RATIO_TTM aligned to publicDate"
    ratios = ratios[ratios["ratioType"] == "RATIO_TTM"].copy()
    ratios["year"] = pd.to_numeric(ratios["year"], errors="coerce").astype("Int64")
    ratios["quarter"] = pd.to_numeric(ratios["quarter"], errors="coerce").astype("Int64")
    publication_column = next(
        (column for column in ("publicDate", "updateDate", "createDate") if column in income.columns),
        None,
    )
    if publication_column is None:
        return empty_fundamentals(), "VCI quarterly RATIO_TTM aligned to publicDate"
    publications = income[["yearReport", "lengthReport", publication_column]].rename(
        columns={"yearReport": "year", "lengthReport": "quarter", publication_column: "published_at"}
    )
    for key in ("year", "quarter"):
        publications[key] = pd.to_numeric(publications[key], errors="coerce").astype("Int64")
    rows = ratios.merge(publications, on=["year", "quarter"], how="left")
    shares = _numeric_column(rows, "numberOfSharesMktCap")
    market_cap = _numeric_column(rows, "marketCap")
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
        "debt_to_equity": "debtPerEquity",
        "gross_margin": "grossMargin",
        "operating_margin": "ebitMargin",
        "net_margin": "afterTaxProfitMargin",
        "current_ratio": "currentRatio",
        "quick_ratio": "quickRatio",
        "dividend_yield": "dividendYield",
        "reported_pe": "pe",
        "reported_pb": "pb",
        "reported_ps": "ps",
        "reported_ev_ebitda": "evToEbitda",
    }
    for target, source in mappings.items():
        rows[target] = _numeric_column(rows, source)
    return (
        normalize_fundamentals(rows),
        "VCI quarterly RATIO_TTM aligned to day after financial-report publicDate",
    )


def _numeric_column(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(float("nan"), index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce")
