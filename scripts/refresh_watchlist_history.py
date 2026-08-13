"""Refresh canonical PostgreSQL price history for one saved watchlist."""
from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
import time

from sqlalchemy.orm import Session

from api.config import env_float
from api.db.session import create_db_engine
from api.instrument_data_routing import resolve_instrument_data_route
from api.market_sessions import latest_completed_venue_session
from api.providers.vietnam_market import (
    create_vietnam_market_provider,
    provider_runtime_label,
)
from api.providers.vietnam_price_loader import VietnamPriceLoader
from api.repositories.sqlalchemy_price_bar_repository import SqlAlchemyPriceBarRepository
from api.repositories.sqlalchemy_instrument_routing_repository import (
    SqlAlchemyInstrumentRoutingRepository,
)
from api.repositories.sqlalchemy_watchlist_repository import SqlAlchemyWatchlistRepository
from api.services.company_price_service import CompanyPriceService
from api.services.price_refresh_service import PriceRefreshAttempt, PriceRefreshService
from api.services.watchlist_service import WatchlistService
from trading_engine.data.yfinance_loader import YFinanceLoader
from trading_engine.types import DataLoadError, DataLoader, PriceFrame


DEFAULT_VN_REQUESTS_PER_MINUTE = 30.0


def _loader_config(price_adapter: str) -> tuple[DataLoader, str, float]:
    if price_adapter == "yfinance":
        return YFinanceLoader(), "yfinance", 0.0
    if price_adapter != "vnstock_data":
        raise ValueError(f"Unsupported equity price adapter: {price_adapter}")
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
        routing_metadata = SqlAlchemyInstrumentRoutingRepository(
            session
        ).get_instrument_routes_metadata(
            tuple(member.instrument_id for member in watchlist.members)
        )
        routes = {
            row.instrument_id: resolve_instrument_data_route(row)
            for row in routing_metadata
        }
        route_adapters = {
            route.price_adapter for route in routes.values()
            if route.fundamental_adapter is not None
        }
        if (
            len(routes) != len(watchlist.members)
            or len(route_adapters) != 1
            or any(route.fundamental_adapter is None for route in routes.values())
        ):
            raise RuntimeError(
                "Automatic refresh requires a non-empty watchlist containing "
                "equities served by one configured data adapter"
            )
        price_adapter = next(iter(route_adapters))
        members = tuple(watchlist.members)
        instrument_ids = tuple(member.instrument_id for member in members)
        members_by_id = {member.instrument_id: member for member in members}
        coverages = {
            row.instrument_id: row
            for row in SqlAlchemyPriceBarRepository(session).list_instrument_coverages(
                instrument_ids,
                next(iter(routes.values())).price_basis,
            )
        }
        refresh_states = {
            row.instrument_id: row
            for row in SqlAlchemyPriceBarRepository(session).list_instrument_refresh_states(
                instrument_ids,
                next(iter(routes.values())).price_basis,
            )
        }
    if not members:
        raise RuntimeError("Watchlist has no companies")

    now = datetime.now(UTC)
    expected = latest_completed_venue_session(
        now, next(iter(routes.values())).schedule
    )
    requested = {
        member.instrument_id: (
            max(
                routes[member.instrument_id].full_history_start,
                coverages[member.instrument_id].last_date - timedelta(days=7),
            )
            if member.instrument_id in coverages
            else routes[member.instrument_id].full_history_start
        )
        for member in members
        if (
            member.instrument_id not in coverages
            or (
                coverages[member.instrument_id].last_date < expected
                and not (
                    member.instrument_id in refresh_states
                    and refresh_states[member.instrument_id].attempted_through >= expected
                    and refresh_states[member.instrument_id].outcome == "checked_no_new_bar"
                )
            )
        )
    }
    total = len(requested)
    print(
        f"WATCHLIST {watchlist_id}: reusing {len(members) - total}/{len(members)}; "
        f"downloading {total}",
        flush=True,
    )
    if not requested:
        print(f"WATCHLIST {watchlist_id}: 0/0 already current", flush=True)
        return

    loader, primary_source, request_interval = _loader_config(price_adapter)
    downloaded: dict[int, PriceFrame] = {}
    errors: dict[int, str] = {}
    for position, (instrument_id, start) in enumerate(requested.items(), start=1):
        ticker = routes[instrument_id].provider_symbol
        try:
            downloaded[instrument_id] = loader.load(
                ticker, start, expected + timedelta(days=1)
            )
        except (DataLoadError, ValueError) as exc:
            errors[instrument_id] = str(exc)
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
                    repository,
                    SqlAlchemyInstrumentRoutingRepository(session),
                ).store_downloaded_histories(
                    downloaded,
                    fetched_at=now,
                )
            attempts = [
                PriceRefreshAttempt(
                    instrument_id=instrument_id,
                    price_basis=routes[instrument_id].price_basis,
                    attempted_through=expected,
                    returned_through=(
                        downloaded[instrument_id].data.index.max().date()
                        if instrument_id in downloaded else None
                    ),
                    outcome=(
                        "current"
                        if instrument_id in downloaded
                        and downloaded[instrument_id].data.index.max().date() >= expected
                        else "checked_no_new_bar"
                        if instrument_id in downloaded
                        else "failed"
                    ),
                    primary_source=primary_source,
                    selected_source=(
                        downloaded[instrument_id].source
                        if instrument_id in downloaded else None
                    ),
                    attempted_at=now,
                    detail=errors.get(instrument_id),
                )
                for instrument_id in requested
            ]
            PriceRefreshService(repository).record_attempts(attempts)
    if downloaded:
        print(f"WATCHLIST {watchlist_id}: stored {stored} rows", flush=True)
    if errors:
        print(
            "Refresh errors: "
            + " | ".join(
                f"{members_by_id[instrument_id].symbol}: {error}"
                for instrument_id, error in errors.items()
            ),
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
