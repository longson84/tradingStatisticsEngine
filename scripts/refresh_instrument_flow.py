"""Refresh stored foreign-investor flow for one exact Instrument."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from api.db.session import create_db_engine, session_scope
from api.instrument_data_routing import resolve_instrument_data_route
from api.market_sessions import latest_completed_venue_session
from api.providers.vietnam_market import (
    VietnamMarketProvider,
    VnstockProvider,
    normalize_foreign_flow_result,
    provider_source_label,
)
from api.repositories.sqlalchemy_instrument_flow_repository import (
    SqlAlchemyInstrumentFlowRepository,
)
from api.repositories.sqlalchemy_instrument_routing_repository import (
    SqlAlchemyInstrumentRoutingRepository,
)
from api.services.instrument_flow_write_service import InstrumentFlowWriteService


OVERLAP_DAYS = 7


def refresh_instrument_flow(
    instrument_id: int,
    mode: str,
    *,
    engine: Engine | None = None,
    provider: VietnamMarketProvider | None = None,
    now: datetime | None = None,
) -> str:
    if mode not in {"incremental", "full"}:
        raise ValueError(f"Unsupported refresh mode: {mode}")
    db_engine = engine or create_db_engine()
    with Session(db_engine) as session:
        repository = SqlAlchemyInstrumentFlowRepository(session)
        instrument = repository.get_instrument(instrument_id)
        metadata = SqlAlchemyInstrumentRoutingRepository(
            session
        ).get_instrument_route_metadata(instrument_id)
        coverage = repository.get_coverage(instrument_id, "foreign")
    if instrument is None or metadata is None:
        raise RuntimeError(f"Unknown instrument: {instrument_id}")
    route = resolve_instrument_data_route(metadata)
    if "foreign_flow" not in route.capabilities:
        raise RuntimeError(f"Instrument {instrument_id} does not support foreign_flow")

    fetched_at = now or datetime.now(UTC)
    if fetched_at.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    end = latest_completed_venue_session(fetched_at, route.schedule)
    start = (
        route.full_history_start
        if mode == "full" or coverage is None
        else coverage.last_date - timedelta(days=OVERLAP_DAYS)
    )
    result = (provider or VnstockProvider()).foreign_flow(
        route.provider_symbol, start, end
    )
    frame = normalize_foreign_flow_result(result)
    source = provider_source_label(result.metadata)
    with session_scope(db_engine) as session:
        InstrumentFlowWriteService(
            SqlAlchemyInstrumentFlowRepository(session),
            SqlAlchemyInstrumentRoutingRepository(session),
        ).store_observations(
            instrument_id,
            "foreign",
            frame,
            source=source,
            fetched_at=fetched_at,
        )
    returned = None if frame.empty else frame["date"].max()
    return f"updated {instrument.symbol} foreign flow through {returned or 'none'}"
