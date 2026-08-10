"""SQLAlchemy implementation of the watchlist repository."""
from __future__ import annotations

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session, selectinload

from api.db.models import Instrument, Watchlist, WatchlistMembership
from api.repositories.watchlist_repository import (
    WatchlistMemberRecord,
    WatchlistRecord,
    WatchlistSummaryRecord,
)


class SqlAlchemyWatchlistRepository:
    def __init__(self, session: Session):
        self._session = session

    def list_watchlists(
        self, market: str | None = None
    ) -> tuple[WatchlistSummaryRecord, ...]:
        statement = (
            select(Watchlist, func.count(WatchlistMembership.id))
            .outerjoin(WatchlistMembership)
            .group_by(Watchlist.id)
            .order_by(Watchlist.market, Watchlist.name_key)
        )
        if market is not None:
            statement = statement.where(Watchlist.market == market)
        return tuple(
            WatchlistSummaryRecord(
                id=watchlist.id,
                name=watchlist.name,
                market=watchlist.market,
                description=watchlist.description,
                member_count=int(member_count),
                created_at=watchlist.created_at,
                updated_at=watchlist.updated_at,
            )
            for watchlist, member_count in self._session.execute(statement)
        )

    def get_watchlist(self, watchlist_id: int) -> WatchlistRecord | None:
        watchlist = self._session.scalar(
            select(Watchlist)
            .where(Watchlist.id == watchlist_id)
            .options(
                selectinload(Watchlist.memberships).selectinload(
                    WatchlistMembership.instrument
                ).selectinload(Instrument.company)
            )
        )
        if watchlist is None:
            return None
        memberships = sorted(
            watchlist.memberships,
            key=lambda row: (row.position, row.instrument.ticker),
        )
        return WatchlistRecord(
            id=watchlist.id,
            name=watchlist.name,
            market=watchlist.market,
            description=watchlist.description,
            created_at=watchlist.created_at,
            updated_at=watchlist.updated_at,
            members=tuple(
                WatchlistMemberRecord(
                    ticker=row.instrument.ticker,
                    company_name=row.instrument.company.display_name,
                    market=row.instrument.market,
                    sector=row.instrument.company.sector,
                    industry=row.instrument.company.industry,
                    exchange=row.instrument.exchange,
                    position=row.position,
                )
                for row in memberships
            ),
        )

    def name_exists(
        self, market: str, name_key: str, exclude_id: int | None = None
    ) -> bool:
        filters = [Watchlist.market == market, Watchlist.name_key == name_key]
        if exclude_id is not None:
            filters.append(Watchlist.id != exclude_id)
        return self._session.scalar(
            select(Watchlist.id).where(*filters).limit(1)
        ) is not None

    def resolve_instrument_ids(
        self, market: str, tickers: tuple[str, ...]
    ) -> dict[str, int]:
        if not tickers:
            return {}
        return {
            ticker: instrument_id
            for ticker, instrument_id in self._session.execute(
                select(Instrument.ticker, Instrument.id).where(
                    Instrument.market == market,
                    Instrument.ticker.in_(tickers),
                    Instrument.is_active.is_(True),
                )
            )
        }

    def create_watchlist(
        self, *, name: str, name_key: str, market: str, description: str
    ) -> int:
        watchlist = Watchlist(
            name=name,
            name_key=name_key,
            market=market,
            description=description,
        )
        self._session.add(watchlist)
        self._session.flush()
        return watchlist.id

    def update_watchlist(
        self, watchlist_id: int, *, name: str, name_key: str, description: str
    ) -> bool:
        result = self._session.execute(
            update(Watchlist)
            .where(Watchlist.id == watchlist_id)
            .values(
                name=name,
                name_key=name_key,
                description=description,
                updated_at=func.now(),
            )
        )
        return bool(result.rowcount)

    def replace_members(
        self, watchlist_id: int, market: str, instrument_ids: tuple[int, ...]
    ) -> None:
        self._session.execute(
            delete(WatchlistMembership).where(
                WatchlistMembership.watchlist_id == watchlist_id
            )
        )
        self._session.add_all(
            WatchlistMembership(
                watchlist_id=watchlist_id,
                instrument_id=instrument_id,
                market=market,
                position=position,
            )
            for position, instrument_id in enumerate(instrument_ids)
        )
        self._session.flush()

    def delete_watchlist(self, watchlist_id: int) -> bool:
        self._session.execute(
            delete(WatchlistMembership).where(
                WatchlistMembership.watchlist_id == watchlist_id
            )
        )
        result = self._session.execute(
            delete(Watchlist).where(Watchlist.id == watchlist_id)
        )
        return bool(result.rowcount)
