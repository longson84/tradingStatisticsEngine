"""Refresh persistent point-in-time fundamentals for one or all universes."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import time
from uuid import uuid4

from sqlalchemy.orm import Session

from api.db.session import create_db_engine
from api.fundamental_provider import fetch_provider_fundamentals
from api.repositories.sqlalchemy_data_operation_repository import (
    SqlAlchemyDataOperationRepository,
)
from api.repositories.sqlalchemy_fundamental_repository import (
    SqlAlchemyFundamentalRepository,
)
from api.repositories.sqlalchemy_instrument_routing_repository import (
    SqlAlchemyInstrumentRoutingRepository,
)
from api.instrument_data_routing import resolve_instrument_data_route
from api.services.fundamental_write_service import FundamentalWriteService
from api.providers.vietnam_fundamentals import VnstockDataFundamentalProvider


REUSE_WINDOW = timedelta(hours=12)


def _recently_refreshed(
    repository: SqlAlchemyFundamentalRepository,
    instrument_id: int,
    started_at: datetime,
    refreshed_after: datetime | None = None,
) -> bool:
    fetched_at = repository.get_latest_fetched_at(instrument_id)
    if fetched_at is None:
        return False
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)
    if refreshed_after is not None:
        return fetched_at >= refreshed_after
    return started_at - fetched_at <= REUSE_WINDOW


def refresh_universe(
    universe: str,
    *,
    us_delay: float,
    vn_delay: float,
    mode: str = "incremental",
    job_id: str | None = None,
    full_run_started_at: datetime | None = None,
) -> None:
    started_at = datetime.now(timezone.utc)
    engine = create_db_engine()
    with Session(engine) as session:
        scope = SqlAlchemyDataOperationRepository(session).get_scope(
            "universe", universe
        )
        if scope is None:
            raise RuntimeError(f"Unknown PostgreSQL universe: {universe}")
        instruments = [
            instrument
            for instrument in scope.instruments
            if instrument.company_id is not None
        ]
        if not instruments:
            raise RuntimeError(
                f"PostgreSQL universe {scope.scope_id} has no active equities"
            )
        routing_metadata = SqlAlchemyInstrumentRoutingRepository(
            session
        ).get_instrument_routes_metadata(
            tuple(instrument.id for instrument in instruments)
        )
        routes = {
            row.instrument_id: resolve_instrument_data_route(row)
            for row in routing_metadata
        }
        fundamental_adapters = {
            route.fundamental_adapter for route in routes.values()
        }
        if (
            len(routes) != len(instruments)
            or len(fundamental_adapters) != 1
            or None in fundamental_adapters
        ):
            raise RuntimeError(
                f"{universe} fundamentals require one configured equity adapter"
            )
        fundamental_adapter = next(iter(fundamental_adapters))
        fundamental_repository = SqlAlchemyFundamentalRepository(session)
        to_fetch = [
            instrument for instrument in instruments
            if not _recently_refreshed(
                fundamental_repository,
                instrument.id,
                started_at,
                refreshed_after=(
                    full_run_started_at or started_at
                    if mode == "full"
                    else None
                ),
            )
        ]
    reused = len(instruments) - len(to_fetch)
    run_id = job_id or uuid4().hex
    vn_provider = (
        VnstockDataFundamentalProvider()
        if fundamental_adapter == "vnstock_data" else None
    )
    delay = vn_delay if fundamental_adapter == "vnstock_data" else us_delay
    source = "vci" if vn_provider is not None else "yfinance"
    provider_version = (
        vn_provider.package_version if vn_provider is not None else None
    )
    with Session(engine) as session, session.begin():
        SqlAlchemyFundamentalRepository(session).create_refresh_run(
            job_id=run_id,
            universe=universe,
            source=source,
            provider_version=provider_version,
            requested_count=len(instruments),
            reused_count=reused,
            started_at=started_at,
        )
    print(
        f"{universe}: reusing {reused}/{len(instruments)} recent fundamental caches; "
        f"downloading {len(to_fetch)}",
        flush=True,
    )
    errors: list[dict[str, str]] = []
    for index, instrument in enumerate(to_fetch, start=1):
        try:
            frame, source, methodology = fetch_provider_fundamentals(
                routes[instrument.id].provider_symbol,
                fundamental_adapter,
                vn_provider=vn_provider,
            )
            with Session(engine) as session, session.begin():
                FundamentalWriteService(
                    SqlAlchemyFundamentalRepository(session)
                ).store_provider_frame(
                    instrument_id=instrument.id,
                    source=source,
                    methodology=methodology,
                    fetched_at=started_at,
                    frame=frame,
                )
        except Exception as exc:
            errors.append({"symbol": instrument.symbol, "error": str(exc)})
        completed = reused + index
        print(
            f"{universe}: {completed}/{len(instruments)} errors={len(errors)}",
            flush=True,
        )
        if index < len(to_fetch):
            time.sleep(delay)
    failed = len(errors)
    succeeded = len(to_fetch) - failed
    status = "failed" if to_fetch and failed == len(to_fetch) else "completed"
    with Session(engine) as session, session.begin():
        SqlAlchemyFundamentalRepository(session).finish_refresh_run(
            job_id=run_id,
            status=status,
            succeeded_count=succeeded,
            failed_count=failed,
            finished_at=datetime.now(timezone.utc),
            error_summary={"errors": errors[:100]} if errors else None,
        )
    if status == "failed":
        raise RuntimeError(f"No fundamentals could be refreshed: {errors[:5]}")
    print(
        f"{universe}: fundamentals complete; refreshed={len(to_fetch) - len(errors)} "
        f"reused={reused} errors={len(errors)}",
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--universe",
        choices=(
            "all", "us2000", "us500", "us100",
            "vnall", "vn100", "vn30", "vnmid", "vnsml",
        ),
        default="all",
    )
    parser.add_argument("--us-delay", type=float, default=0.25)
    parser.add_argument("--vn-delay", type=float, default=4.1)
    parser.add_argument("--mode", choices=("incremental", "full"), default="incremental")
    parser.add_argument("--job-id")
    args = parser.parse_args()
    order = (
        "US2000", "US500", "US100", "VNALL", "VN100", "VN30", "VNMID", "VNSML",
    )
    if args.universe == "all":
        full_run_started_at = datetime.now(timezone.utc)
        for universe in order:
            run_id = f"{args.job_id}:{universe}" if args.job_id else None
            refresh_universe(
                universe,
                us_delay=args.us_delay,
                vn_delay=args.vn_delay,
                mode=args.mode,
                job_id=run_id,
                full_run_started_at=full_run_started_at,
            )
        return
    universe = args.universe.upper()
    refresh_universe(
        universe,
        us_delay=args.us_delay,
        vn_delay=args.vn_delay,
        mode=args.mode,
        job_id=args.job_id,
    )


if __name__ == "__main__":
    main()
