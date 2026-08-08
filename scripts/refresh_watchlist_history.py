"""Refresh canonical PostgreSQL price history for one saved watchlist."""
from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
import time

from sqlalchemy.orm import Session

from api.config import env_float
from api.db.session import create_db_engine
from api.market_sessions import latest_completed_session
from api.providers.vietnam_market import (
    create_vietnam_market_provider,
    provider_runtime_label,
)
from api.providers.vietnam_price_loader import VietnamPriceLoader
from api.repositories.sqlalchemy_price_bar_repository import SqlAlchemyPriceBarRepository
from api.repositories.sqlalchemy_watchlist_repository import SqlAlchemyWatchlistRepository
from api.services.company_price_service import (
    CompanyPriceService,
    FULL_HISTORY_START,
)
from api.services.price_history_service import DEFAULT_PRICE_BASIS
from api.services.price_refresh_service import PriceRefreshAttempt, PriceRefreshService
from api.services.watchlist_service import WatchlistService
from trading_engine.data.yfinance_loader import YFinanceLoader
from trading_engine.types import DataLoadError, DataLoader, PriceFrame


DEFAULT_VN_REQUESTS_PER_MINUTE = 30.0


def _loader_config(market: str) -> tuple[DataLoader, str, float]:
    if market == "US":
        return YFinanceLoader(), "yfinance", 0.0
    provider = create_vietnam_market_provider(require_sponsored=True)
    requests_per_minute = env_float(
        "VNSTOCK_REQUESTS_PER_MINUTE", DEFAULT_VN_REQUESTS_PER_MINUTE
    )
    if requests_per_minute <= 0:
        raise ValueError("VNSTOCK_REQUESTS_PER_MINUTE must be greater than zero")
    return (
        VietnamPriceLoader(provider),
        provider_runtime_label(provider),
        60.0 / requests_per_minute,
    )


def refresh_watchlist(watchlist_id: int) -> None:
    engine = create_db_engine()
    with Session(engine) as session:
        watchlist = WatchlistService(
            SqlAlchemyWatchlistRepository(session)
        ).get_watchlist(watchlist_id)
        tickers = tuple(member.ticker for member in watchlist.members)
        coverages = {
            row.ticker: row
            for row in SqlAlchemyPriceBarRepository(session).list_symbol_coverages(
                watchlist.market,
                tickers,
                DEFAULT_PRICE_BASIS[watchlist.market],
            )
        }
        refresh_states = {
            row.ticker: row
            for row in SqlAlchemyPriceBarRepository(session).list_refresh_states(
                watchlist.market,
                tickers,
                DEFAULT_PRICE_BASIS[watchlist.market],
            )
        }
    if not tickers:
        raise RuntimeError("Watchlist has no companies")

    now = datetime.now(UTC)
    expected = latest_completed_session(now, watchlist.market)
    requested = {
        ticker: (
            max(FULL_HISTORY_START, coverages[ticker].last_date - timedelta(days=7))
            if ticker in coverages
            else FULL_HISTORY_START
        )
        for ticker in tickers
        if (
            ticker not in coverages
            or (
                coverages[ticker].last_date < expected
                and not (
                    ticker in refresh_states
                    and refresh_states[ticker].attempted_through >= expected
                    and refresh_states[ticker].outcome == "checked_no_new_bar"
                )
            )
        )
    }
    total = len(requested)
    print(
        f"WATCHLIST {watchlist_id}: reusing {len(tickers) - total}/{len(tickers)}; "
        f"downloading {total}",
        flush=True,
    )
    if not requested:
        print(f"WATCHLIST {watchlist_id}: 0/0 already current", flush=True)
        return

    loader, primary_source, request_interval = _loader_config(watchlist.market)
    downloaded: dict[str, PriceFrame] = {}
    errors: dict[str, str] = {}
    for position, (ticker, start) in enumerate(requested.items(), start=1):
        try:
            downloaded[ticker] = loader.load(
                ticker, start, expected + timedelta(days=1)
            )
        except (DataLoadError, ValueError) as exc:
            errors[ticker] = str(exc)
        print(
            f"WATCHLIST {watchlist_id}: {position}/{total} errors={len(errors)}",
            flush=True,
        )
        if request_interval > 0 and position < total:
            time.sleep(request_interval)

    with Session(engine) as session:
        with session.begin():
            repository = SqlAlchemyPriceBarRepository(session)
            if downloaded:
                stored = CompanyPriceService(
                    repository, {}
                ).store_downloaded_histories(
                    watchlist.market,
                    downloaded,
                    fetched_at=now,
                )
            attempts = [
                PriceRefreshAttempt(
                    ticker=ticker,
                    attempted_through=expected,
                    returned_through=(
                        downloaded[ticker].data.index.max().date()
                        if ticker in downloaded else None
                    ),
                    outcome=(
                        "current"
                        if ticker in downloaded
                        and downloaded[ticker].data.index.max().date() >= expected
                        else "checked_no_new_bar"
                        if ticker in downloaded
                        else "failed"
                    ),
                    primary_source=primary_source,
                    selected_source=(
                        downloaded[ticker].source if ticker in downloaded else None
                    ),
                    attempted_at=now,
                    detail=errors.get(ticker),
                )
                for ticker in requested
            ]
            PriceRefreshService(repository).record_attempts(
                "VNALL" if watchlist.market == "VN" else "US500",
                attempts,
            )
    if downloaded:
        print(f"WATCHLIST {watchlist_id}: stored {stored} rows", flush=True)
    if errors:
        print(
            "Refresh errors: "
            + " | ".join(f"{ticker}: {error}" for ticker, error in errors.items()),
            flush=True,
        )
    if not downloaded:
        raise RuntimeError("Every watchlist company refresh failed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--watchlist-id", type=int, required=True)
    args = parser.parse_args()
    refresh_watchlist(args.watchlist_id)


if __name__ == "__main__":
    main()
