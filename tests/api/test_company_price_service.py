from __future__ import annotations

from datetime import UTC, date, datetime

import pandas as pd
import pytest

from api.repositories.price_bar_repository import (
    PriceBarRecord,
    SymbolPriceCoverageRecord,
)
from api.services.company_price_service import (
    CompanyPriceService,
    UnknownCompanyError,
    latest_completed_session,
)
from trading_engine.types import PriceFrame


class StubRepository:
    def __init__(self, last_date: date | None):
        self.exists = True
        self.last_date = last_date
        self.records = [] if last_date is None else [self._row(last_date, 100.0)]
        self.writes = []

    def instrument_exists(self, market, ticker):
        return self.exists

    def get_symbol_coverage(self, market, ticker, price_basis):
        if self.last_date is None:
            return None
        return SymbolPriceCoverageRecord(
            ticker=ticker,
            market=market,
            first_date=self.records[0].trading_date,
            last_date=self.last_date,
            row_count=len(self.records),
            source="yfinance",
            fetched_at=datetime(2026, 8, 4, tzinfo=UTC),
        )

    def iter_symbol_bars(self, query):
        return tuple(self.records)

    def list_symbol_coverages(self, market, tickers, price_basis):
        coverage = self.get_symbol_coverage(market, "MSFT", price_basis)
        return (coverage,) if coverage is not None and "MSFT" in tickers else ()

    def iter_symbol_set_bars(self, query):
        return tuple(row for row in self.records if row.ticker in query.tickers)

    def upsert_bars(self, records):
        self.writes = list(records)
        for record in self.writes:
            self.records = [row for row in self.records if row.trading_date != record.trading_date]
            self.records.append(self._row(record.trading_date, record.close))
        self.records.sort(key=lambda row: row.trading_date)
        self.last_date = self.records[-1].trading_date
        return len(self.writes)

    @staticmethod
    def _row(day, close):
        return PriceBarRecord(
            ticker="MSFT",
            market="US",
            trading_date=day,
            open=close,
            high=close,
            low=close,
            close=close,
            volume=1_000.0,
            currency="USD",
            price_scale=1,
            price_basis="adjusted",
            source="yfinance",
            fetched_at=datetime(2026, 8, 4, tzinfo=UTC),
        )


class StubLoader:
    def __init__(self, day: date):
        self.day = day
        self.calls = []

    def load(self, symbol, start, end):
        self.calls.append((symbol, start, end))
        index = pd.DatetimeIndex([self.day], name="date")
        return PriceFrame(
            symbol=symbol,
            data=pd.DataFrame({
                "open": [101.0], "high": [101.0], "low": [101.0],
                "close": [101.0], "volume": [2_000.0],
            }, index=index),
            source="yfinance",
        )


def test_fresh_postgresql_history_does_not_download():
    expected = date(2026, 8, 3)
    repository = StubRepository(expected)
    loader = StubLoader(expected)
    service = CompanyPriceService(repository, {"US": loader, "VN": loader})

    result = service.get_current_history(
        "US", "MSFT", now=datetime(2026, 8, 4, 12, tzinfo=UTC)
    )

    assert loader.calls == []
    assert result.data_last_session == expected
    assert result.refreshed is False
    assert result.is_stale is False


def test_stale_ticker_downloads_only_that_ticker_and_upserts():
    repository = StubRepository(date(2026, 7, 31))
    loader = StubLoader(date(2026, 8, 3))
    service = CompanyPriceService(repository, {"US": loader, "VN": loader})

    result = service.get_current_history(
        "US", "MSFT", now=datetime(2026, 8, 4, 12, tzinfo=UTC)
    )

    assert len(loader.calls) == 1
    assert loader.calls[0][0] == "MSFT"
    assert repository.writes
    assert result.refreshed is True
    assert result.data_last_session == date(2026, 8, 3)
    assert result.is_stale is False


def test_unknown_company_is_rejected_before_provider_access():
    repository = StubRepository(None)
    repository.exists = False
    loader = StubLoader(date(2026, 8, 3))
    service = CompanyPriceService(repository, {"US": loader, "VN": loader})

    with pytest.raises(UnknownCompanyError):
        service.get_current_history("US", "UNKNOWN")
    assert loader.calls == []


def test_stored_histories_report_stale_and_missing_without_provider_calls():
    repository = StubRepository(date(2026, 7, 31))
    loader = StubLoader(date(2026, 8, 3))
    service = CompanyPriceService(repository, {"US": loader, "VN": loader})

    result = service.get_stored_histories(
        "US",
        ["MSFT", "AAPL"],
        now=datetime(2026, 8, 4, 12, tzinfo=UTC),
    )

    assert tuple(result.prices) == ("MSFT",)
    assert result.stale_tickers == ("MSFT",)
    assert result.missing_tickers == ("AAPL",)
    assert loader.calls == []


def test_latest_completed_session_respects_market_close_and_weekend():
    assert latest_completed_session(
        datetime(2026, 8, 3, 7, tzinfo=UTC), "VN"
    ) == date(2026, 7, 31)
    assert latest_completed_session(
        datetime(2026, 8, 3, 9, tzinfo=UTC), "VN"
    ) == date(2026, 8, 3)


@pytest.mark.parametrize(
    ("market", "ticker", "currency", "scale", "basis", "source"),
    [
        ("US", "MSFT", "USD", 1, "adjusted", "yfinance"),
        ("VN", "FPT", "VND", 1_000, "provider_unspecified", "vnstock-vci"),
    ],
)
def test_store_downloaded_histories_uses_canonical_market_metadata(
    market, ticker, currency, scale, basis, source
):
    repository = StubRepository(None)
    service = CompanyPriceService(repository, {})
    frame = PriceFrame(
        symbol=ticker,
        data=pd.DataFrame(
            {
                "open": [10.0],
                "high": [11.0],
                "low": [9.0],
                "close": [10.5],
                "volume": [1_000.0],
            },
            index=pd.DatetimeIndex([date(2026, 8, 3)], name="date"),
        ),
        source=source,
    )
    fetched_at = datetime(2026, 8, 4, tzinfo=UTC)

    stored = service.store_downloaded_histories(
        market, {ticker: frame}, fetched_at=fetched_at
    )

    assert stored == 1
    written = repository.writes[0]
    assert written.market == market
    assert written.ticker == ticker
    assert written.currency == currency
    assert written.price_scale == scale
    assert written.price_basis == basis
    assert written.source == source
    assert written.fetched_at == fetched_at
