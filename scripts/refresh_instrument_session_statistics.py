"""Refresh one exact-period VCI session-statistics snapshot."""
from datetime import UTC, date, datetime

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from api.db.session import create_db_engine, session_scope
from api.instrument_data_routing import resolve_instrument_data_route
from api.providers.vietnam_market import (
    VietnamMarketProvider,
    VnstockProvider,
    normalize_session_stats_result,
    provider_source_label,
)
from api.repositories.sqlalchemy_instrument_routing_repository import (
    SqlAlchemyInstrumentRoutingRepository,
)
from api.repositories.sqlalchemy_session_statistics_repository import (
    SqlAlchemySessionStatisticsRepository,
)
from api.services.session_statistics_write_service import (
    SessionStatisticsWriteService,
)


def refresh_instrument_session_statistics(
    instrument_id: int,
    period_start: date,
    period_end: date,
    *,
    engine: Engine | None = None,
    provider: VietnamMarketProvider | None = None,
    now: datetime | None = None,
) -> str:
    db_engine = engine or create_db_engine()
    with Session(db_engine) as session:
        repository = SqlAlchemySessionStatisticsRepository(session)
        instrument = repository.get_instrument(instrument_id)
        metadata = SqlAlchemyInstrumentRoutingRepository(
            session
        ).get_instrument_route_metadata(instrument_id)
    if instrument is None or metadata is None:
        raise RuntimeError(f"Unknown instrument: {instrument_id}")
    route = resolve_instrument_data_route(metadata)
    if "session_stats" not in route.capabilities:
        raise RuntimeError(
            f"Instrument {instrument_id} does not support session_stats"
        )
    result = (provider or VnstockProvider()).session_stats(
        route.provider_symbol, period_start, period_end
    )
    metrics = normalize_session_stats_result(result)
    fetched_at = now or datetime.now(UTC)
    if fetched_at.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    with session_scope(db_engine) as session:
        SessionStatisticsWriteService(
            SqlAlchemySessionStatisticsRepository(session),
            SqlAlchemyInstrumentRoutingRepository(session),
        ).store_snapshot(
            instrument_id,
            result.metadata.symbol,
            period_start,
            period_end,
            metrics,
            source=provider_source_label(result.metadata),
            fetched_at=fetched_at,
        )
    return (
        f"updated {instrument.symbol} session statistics for {period_start} "
        f"through {period_end}"
    )
