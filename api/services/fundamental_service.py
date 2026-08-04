"""Point-in-time fundamental use cases independent from SQLAlchemy and FastAPI."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

import pandas as pd

from api.repositories.fundamental_repository import (
    FundamentalRepository,
    FundamentalStatusRecord,
)


IDENTITY_COLUMNS = ("effective_date", "period_end", "period")
VALUE_COLUMNS = (
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
)
FUNDAMENTAL_COLUMNS = IDENTITY_COLUMNS + VALUE_COLUMNS

_FACT_COLUMNS = {
    "eps_ttm": "eps_ttm",
    "book_value_per_share": "book_value_per_share",
    "revenue_ttm": "revenue_ttm",
    "gross_profit_ttm": "gross_profit_ttm",
    "operating_income_ttm": "operating_income_ttm",
    "net_income_ttm": "net_income_ttm",
    "shares_outstanding": "shares_outstanding",
    "total_equity": "equity",
    "total_assets": "total_assets",
    "total_debt": "total_debt",
    "roe": "roe",
    "roa": "roa",
    "debt_to_equity": "debt_to_equity",
    "gross_margin": "gross_margin",
    "operating_margin": "operating_margin",
    "net_margin": "net_margin",
    "current_ratio": "current_ratio",
    "quick_ratio": "quick_ratio",
}
_VALUATION_COLUMNS = {
    "market_cap": "market_cap",
    "dividend_yield": "dividend_yield",
    "pe": "reported_pe",
    "pb": "reported_pb",
    "ps": "reported_ps",
    "ev_ebitda": "reported_ev_ebitda",
}


class FundamentalsNotFoundError(ValueError):
    pass


@dataclass(frozen=True)
class FundamentalHistoryMetadata:
    sources: tuple[str, ...]
    methodologies: tuple[str, ...]
    fetched_at: datetime
    first_effective_date: date
    last_effective_date: date
    snapshot_count: int
    fields: tuple[str, ...]


@dataclass(frozen=True)
class FundamentalHistory:
    market: str
    ticker: str
    snapshots: pd.DataFrame
    metadata: FundamentalHistoryMetadata


class FundamentalService:
    def __init__(self, repository: FundamentalRepository):
        self._repository = repository

    def get_symbol_history(self, market: str, ticker: str) -> FundamentalHistory:
        normalized_market = market.upper().strip()
        normalized_ticker = ticker.upper().strip()
        if normalized_market not in {"US", "VN"} or not normalized_ticker:
            raise FundamentalsNotFoundError("A valid market and ticker are required")
        if not self._repository.instrument_exists(
            normalized_market, normalized_ticker
        ):
            raise FundamentalsNotFoundError(
                f"Unknown instrument: {normalized_market}-{normalized_ticker}"
            )
        reports = self._repository.list_reports(
            normalized_market, normalized_ticker
        )
        if not reports:
            raise FundamentalsNotFoundError(
                f"No stored fundamentals for {normalized_market}-{normalized_ticker}"
            )
        rows: dict[date, dict[str, object]] = {}
        report_dates: dict[int, date] = {}
        for report in reports:
            report_dates[report.id] = report.effective_session_date
            row = rows.setdefault(report.effective_session_date, {
                column: pd.NA for column in FUNDAMENTAL_COLUMNS
            })
            row["effective_date"] = pd.Timestamp(report.effective_session_date)
            if report.period_end is not None:
                row["period_end"] = pd.Timestamp(report.period_end)
            if report.period_label:
                row["period"] = report.period_label
        for fact in self._repository.list_facts(tuple(report_dates)):
            column = _FACT_COLUMNS.get(fact.metric_code)
            if column:
                rows[report_dates[fact.report_id]][column] = float(fact.value)
        valuations = self._repository.list_valuations(
            normalized_market, normalized_ticker
        )
        for valuation in valuations:
            column = _VALUATION_COLUMNS.get(valuation.metric_code)
            if not column:
                continue
            row = rows.setdefault(valuation.effective_session_date, {
                key: pd.NA for key in FUNDAMENTAL_COLUMNS
            })
            row["effective_date"] = pd.Timestamp(
                valuation.effective_session_date
            )
            row[column] = float(valuation.value)

        snapshots = pd.DataFrame(rows.values(), columns=FUNDAMENTAL_COLUMNS)
        snapshots = snapshots.sort_values("effective_date").reset_index(drop=True)
        for column in VALUE_COLUMNS:
            snapshots[column] = pd.to_numeric(snapshots[column], errors="coerce")
        sources = {report.source for report in reports}
        sources.update(row.source for row in valuations)
        methods = {report.methodology for report in reports if report.methodology}
        methods.update(row.methodology for row in valuations if row.methodology)
        fetched = [report.fetched_at for report in reports]
        fetched.extend(row.fetched_at for row in valuations)
        populated_fields = tuple(
            column for column in VALUE_COLUMNS if snapshots[column].notna().any()
        )
        return FundamentalHistory(
            market=normalized_market,
            ticker=normalized_ticker,
            snapshots=snapshots,
            metadata=FundamentalHistoryMetadata(
                sources=tuple(sorted(sources)),
                methodologies=tuple(sorted(methods)),
                fetched_at=max(fetched),
                first_effective_date=snapshots["effective_date"].min().date(),
                last_effective_date=snapshots["effective_date"].max().date(),
                snapshot_count=len(snapshots),
                fields=populated_fields,
            ),
        )

    def get_universe_status(
        self, universe: str
    ) -> FundamentalStatusRecord | None:
        normalized = universe.upper().strip()
        if not normalized:
            return None
        return self._repository.get_universe_status(normalized)
