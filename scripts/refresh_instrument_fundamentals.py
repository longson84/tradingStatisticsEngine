"""Refresh canonical fundamentals for one exact instrument ID."""
from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from api.db.session import create_db_engine
from api.fundamental_provider import fetch_provider_fundamentals
from api.instrument_data_routing import resolve_instrument_data_route
from api.providers.vietnam_fundamentals import VnstockDataFundamentalProvider
from api.repositories.sqlalchemy_fundamental_repository import (
    SqlAlchemyFundamentalRepository,
)
from api.repositories.sqlalchemy_instrument_routing_repository import (
    SqlAlchemyInstrumentRoutingRepository,
)
from api.services.fundamental_write_service import FundamentalWriteService


REUSE_WINDOW = timedelta(hours=12)


def refresh_instrument_fundamentals(
    instrument_id: int,
    mode: str,
    *,
    engine: Engine | None = None,
    vn_provider: VnstockDataFundamentalProvider | None = None,
) -> str:
    db_engine = engine or create_db_engine()
    fetched_at = datetime.now(UTC)
    with Session(db_engine) as session:
        routing_metadata = SqlAlchemyInstrumentRoutingRepository(
            session
        ).get_instrument_route_metadata(instrument_id)
        if routing_metadata is None:
            raise RuntimeError(f"Unknown instrument: {instrument_id}")
        route = resolve_instrument_data_route(routing_metadata)
        adapter = route.fundamental_adapter
        if adapter is None:
            raise RuntimeError(
                f"Instrument {instrument_id} does not support fundamentals updates"
            )
        repository = SqlAlchemyFundamentalRepository(session)
        latest = repository.get_latest_fetched_at(instrument_id)
        if (
            mode == "incremental"
            and latest is not None
            and fetched_at - _as_utc(latest) <= REUSE_WINDOW
        ):
            return "reused recent canonical fundamentals"

    provider = (
        vn_provider or VnstockDataFundamentalProvider()
        if adapter == "vnstock_data"
        else None
    )
    frame, source, methodology = fetch_provider_fundamentals(
        route.provider_symbol,
        adapter,
        vn_provider=provider,
    )
    with Session(db_engine) as session, session.begin():
        result = FundamentalWriteService(
            SqlAlchemyFundamentalRepository(session)
        ).store_provider_frame(
            instrument_id=instrument_id,
            source=source,
            methodology=methodology,
            fetched_at=fetched_at,
            frame=frame,
        )
    return (
        f"stored {result.report_count} reports and "
        f"{result.fact_count} facts from {source}"
    )


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instrument-id", type=int, required=True)
    parser.add_argument("--mode", choices=("incremental", "full"), default="incremental")
    parser.add_argument("--database-url", default=None)
    args = parser.parse_args()
    detail = refresh_instrument_fundamentals(
        args.instrument_id,
        args.mode,
        engine=create_db_engine(args.database_url),
    )
    print(detail, flush=True)


if __name__ == "__main__":
    main()
