"""SQLAlchemy close-only projection for Universe statistics."""
from __future__ import annotations

from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from api.db.models import Instrument, PriceBar
from api.repositories.universe_stats_repository import (
    UniverseStatsCloseQuery,
    UniverseStatsCloseRecord,
)


class SqlAlchemyUniverseStatsRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def iter_closes(
        self, query: UniverseStatsCloseQuery
    ):
        if not query.instrument_price_bases:
            return
        statement = (
            select(
                PriceBar.instrument_id,
                PriceBar.trading_date,
                PriceBar.close,
                PriceBar.source,
                PriceBar.fetched_at,
            )
            .join(Instrument, Instrument.id == PriceBar.instrument_id)
            .where(
                Instrument.is_active.is_(True),
                tuple_(PriceBar.instrument_id, PriceBar.price_basis).in_(
                    query.instrument_price_bases
                ),
                PriceBar.trading_date >= query.start,
                PriceBar.trading_date <= query.end,
            )
            .order_by(PriceBar.instrument_id, PriceBar.trading_date)
            .execution_options(yield_per=10_000)
        )
        for row in self._session.execute(statement):
            yield UniverseStatsCloseRecord(
                instrument_id=row.instrument_id,
                trading_date=row.trading_date,
                close=float(row.close),
                source=row.source,
                fetched_at=row.fetched_at,
            )
