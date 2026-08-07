"""Refresh persistent point-in-time fundamentals for one or all universes."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import time
from uuid import uuid4

from sqlalchemy.orm import Session

from api.db.session import create_db_engine
from api.fundamental_provider import fetch_provider_fundamentals
from api.repositories.company_repository import CompanyQuery
from api.repositories.sqlalchemy_company_repository import (
    SqlAlchemyCompanyRepository,
)
from api.repositories.sqlalchemy_fundamental_repository import (
    SqlAlchemyFundamentalRepository,
)
from api.services.fundamental_write_service import FundamentalWriteService


REUSE_WINDOW = timedelta(hours=12)


def _recently_refreshed(
    repository: SqlAlchemyFundamentalRepository,
    symbol: str,
    market: str,
    started_at: datetime,
    refreshed_after: datetime | None = None,
) -> bool:
    fetched_at = repository.get_latest_fetched_at(market, symbol)
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
    delay: float,
    mode: str = "incremental",
    job_id: str | None = None,
    full_run_started_at: datetime | None = None,
) -> None:
    market = "VN" if universe.startswith("VN") else "US"
    started_at = datetime.now(timezone.utc)
    engine = create_db_engine()
    with Session(engine) as session:
        company_repository = SqlAlchemyCompanyRepository(session)
        companies, _ = company_repository.list_companies(CompanyQuery(
            market=market,
            universe=universe,
            limit=5_000,
        ))
        symbols = [company.ticker for company in companies]
        fundamental_repository = SqlAlchemyFundamentalRepository(session)
        to_fetch = [
            symbol for symbol in symbols
            if not _recently_refreshed(
                fundamental_repository,
                symbol,
                market,
                started_at,
                refreshed_after=(
                    full_run_started_at or started_at
                    if mode == "full"
                    else None
                ),
            )
        ]
    reused = len(symbols) - len(to_fetch)
    run_id = job_id or uuid4().hex
    source = "vnstock-vci-4.0.5" if market == "VN" else "yfinance"
    provider_version = "4.0.5" if market == "VN" else None
    with Session(engine) as session, session.begin():
        SqlAlchemyFundamentalRepository(session).create_refresh_run(
            job_id=run_id,
            universe=universe,
            source=source,
            provider_version=provider_version,
            requested_count=len(symbols),
            reused_count=reused,
            started_at=started_at,
        )
    print(
        f"{universe}: reusing {reused}/{len(symbols)} recent fundamental caches; "
        f"downloading {len(to_fetch)}",
        flush=True,
    )
    errors: list[dict[str, str]] = []
    for index, symbol in enumerate(to_fetch, start=1):
        try:
            frame, source, methodology = fetch_provider_fundamentals(
                symbol, market
            )
            with Session(engine) as session, session.begin():
                FundamentalWriteService(
                    SqlAlchemyFundamentalRepository(session)
                ).store_provider_frame(
                    market=market,
                    ticker=symbol,
                    source=source,
                    methodology=methodology,
                    fetched_at=started_at,
                    frame=frame,
                )
        except Exception as exc:
            errors.append({"symbol": symbol, "error": str(exc)})
        completed = reused + index
        print(
            f"{universe}: {completed}/{len(symbols)} errors={len(errors)}",
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
        "--market",
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
        ("US2000", args.us_delay),
        ("US500", args.us_delay),
        ("US100", args.us_delay),
        ("VNALL", args.vn_delay),
        ("VN100", args.vn_delay),
        ("VN30", args.vn_delay),
        ("VNMID", args.vn_delay),
        ("VNSML", args.vn_delay),
    )
    if args.market == "all":
        full_run_started_at = datetime.now(timezone.utc)
        for universe, delay in order:
            run_id = f"{args.job_id}:{universe}" if args.job_id else None
            refresh_universe(
                universe,
                delay=delay,
                mode=args.mode,
                job_id=run_id,
                full_run_started_at=full_run_started_at,
            )
        return
    universe = args.market.upper()
    delay = args.vn_delay if universe.startswith("VN") else args.us_delay
    refresh_universe(
        universe, delay=delay, mode=args.mode, job_id=args.job_id
    )


if __name__ == "__main__":
    main()
