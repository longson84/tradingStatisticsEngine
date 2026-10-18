"""Refresh daily VCI trade statistics for one Instrument and explicit period."""
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from api.db.session import create_db_engine, session_scope
from api.market_sessions import latest_requested_venue_session
from api.providers.vietnam_market import (
    VietnamMarketProvider,
    VnstockProvider,
    normalize_trade_history_result,
    provider_source_label,
)
from api.repositories.sqlalchemy_instrument_routing_repository import (
    SqlAlchemyInstrumentRoutingRepository,
)
from api.repositories.sqlalchemy_trade_statistics_repository import (
    SqlAlchemyTradeStatisticsRepository,
)
from api.services.trade_statistics_service import resolve_trade_statistics_instrument
from api.services.trade_statistics_write_service import TradeStatisticsWriteService


def refresh_instrument_trade_statistics(
    instrument_id: int,
    period_start: date,
    period_end: date,
    *,
    mode: str = "full",
    engine: Engine | None = None,
    provider: VietnamMarketProvider | None = None,
    now: datetime | None = None,
) -> str:
    if period_start > period_end:
        raise ValueError("period_start must be on or before period_end")
    if now is not None and now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    if mode not in {"incremental", "full"}:
        raise ValueError("mode must be incremental or full")
    current = now or datetime.now(UTC)
    db_engine = engine or create_db_engine()
    with Session(db_engine) as session:
        repository = SqlAlchemyTradeStatisticsRepository(session)
        instrument, route = resolve_trade_statistics_instrument(
            repository,
            SqlAlchemyInstrumentRoutingRepository(session),
            instrument_id,
        )
        fetch_start = period_start
        if mode == "incremental":
            stored = repository.list_rows(instrument_id, period_start, period_end)
            latest = stored[-1].trading_date if stored else None
            target = latest_requested_venue_session(
                period_end, current, route.schedule,
            )
            if latest is not None and latest >= target:
                return (
                    f"{instrument.symbol} trade statistics requested through {period_end} "
                    f"are already covered through {latest}"
                )
            if latest is not None:
                fetch_start = max(period_start, latest + timedelta(days=1))
    result = (provider or VnstockProvider()).trade_history(
        route.provider_symbol, fetch_start, period_end,
    )
    rows = normalize_trade_history_result(result)
    fetched_at = current
    with session_scope(db_engine) as session:
        stored_count = TradeStatisticsWriteService(
            SqlAlchemyTradeStatisticsRepository(session),
            SqlAlchemyInstrumentRoutingRepository(session),
        ).store_rows(
            instrument_id, result.metadata.symbol, rows,
            source=provider_source_label(result.metadata), fetched_at=fetched_at,
        )
    detail = (
        f"updated {instrument.symbol} trade statistics for {period_start} "
        f"through {period_end}: stored {stored_count} rows; returned sessions "
        f"{rows.iloc[0]['trading_date']} through {rows.iloc[-1]['trading_date']}"
    )
    if mode == "incremental" and fetch_start != period_start:
        detail += f"; incremental tail {fetch_start} through {period_end}"
    return detail
