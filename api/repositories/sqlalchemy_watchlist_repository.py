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

    def list_watchlists(self) -> tuple[WatchlistSummaryRecord, ...]:
        watchlists = self._session.scalars(
            select(Watchlist)
            .options(*self._load_options())
            .order_by(Watchlist.name_key)
        ).all()
        records = (self._record(watchlist) for watchlist in watchlists)
        return tuple(
            WatchlistSummaryRecord(
                id=record.id,
                name=record.name,
                description=record.description,
                member_count=len(record.members),
                instrument_types=record.instrument_types,
                equity_count=record.equity_count,
                crypto_spot_count=record.crypto_spot_count,
                reference_rate_count=record.reference_rate_count,
                market_index_count=record.market_index_count,
                created_at=record.created_at,
                updated_at=record.updated_at,
            )
            for record in records
        )

    def get_watchlist(self, watchlist_id: int) -> WatchlistRecord | None:
        watchlist = self._session.scalar(
            select(Watchlist)
            .where(Watchlist.id == watchlist_id)
            .options(*self._load_options())
        )
        return self._record(watchlist) if watchlist is not None else None

    def name_exists(self, name_key: str, exclude_id: int | None = None) -> bool:
        filters = [Watchlist.name_key == name_key]
        if exclude_id is not None:
            filters.append(Watchlist.id != exclude_id)
        return self._session.scalar(
            select(Watchlist.id).where(*filters).limit(1)
        ) is not None

    def resolve_active_instrument_ids(
        self, instrument_ids: tuple[int, ...]
    ) -> set[int]:
        if not instrument_ids:
            return set()
        return set(self._session.scalars(
            select(Instrument.id).where(
                Instrument.id.in_(instrument_ids),
                Instrument.is_active.is_(True),
            )
        ))

    def create_watchlist(
        self, *, name: str, name_key: str, description: str
    ) -> int:
        watchlist = Watchlist(
            name=name,
            name_key=name_key,
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
        self, watchlist_id: int, instrument_ids: tuple[int, ...]
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

    @staticmethod
    def _load_options():
        instrument = selectinload(Watchlist.memberships).selectinload(
            WatchlistMembership.instrument
        )
        return (
            instrument.selectinload(Instrument.company),
            instrument.selectinload(Instrument.venue),
            instrument.selectinload(Instrument.base_asset),
            instrument.selectinload(Instrument.quote_asset),
        )

    @staticmethod
    def _record(watchlist: Watchlist) -> WatchlistRecord:
        memberships = sorted(
            watchlist.memberships,
            key=lambda row: (row.position, row.instrument_id),
        )
        return WatchlistRecord(
            id=watchlist.id,
            name=watchlist.name,
            description=watchlist.description,
            created_at=watchlist.created_at,
            updated_at=watchlist.updated_at,
            members=tuple(
                WatchlistMemberRecord(
                    instrument_id=row.instrument.id,
                    symbol=row.instrument.ticker,
                    instrument_type=row.instrument.instrument_type,
                    company_id=row.instrument.company_id,
                    company_name=(
                        row.instrument.company.display_name
                        if row.instrument.company is not None else None
                    ),
                    sector=(
                        row.instrument.company.sector
                        if row.instrument.company is not None else None
                    ),
                    industry=(
                        row.instrument.company.industry
                        if row.instrument.company is not None else None
                    ),
                    venue_code=(
                        row.instrument.venue.code
                        if row.instrument.venue is not None else None
                    ),
                    venue_name=(
                        row.instrument.venue.name
                        if row.instrument.venue is not None else None
                    ),
                    base_asset=(
                        row.instrument.base_asset.canonical_code
                        if row.instrument.base_asset is not None else None
                    ),
                    quote_asset=(
                        row.instrument.quote_asset.canonical_code
                        if row.instrument.quote_asset is not None else None
                    ),
                    currency=row.instrument.currency,
                    position=row.position,
                )
                for row in memberships
            ),
        )
