"""SQLAlchemy projection for canonical instrument universes."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from api.db.models import Instrument, Universe, UniverseMembership, UniverseSyncRun
from api.repositories.universe_repository import (
    UniverseCatalogRecord,
    UniverseSyncRunPage,
    UniverseSyncRunRecord,
)


class SqlAlchemyUniverseRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_universes(self) -> tuple[UniverseCatalogRecord, ...]:
        universes = self._session.scalars(
            select(Universe)
            .options(
                selectinload(Universe.memberships)
                .selectinload(UniverseMembership.instrument)
                .selectinload(Instrument.venue)
            )
            .order_by(Universe.name, Universe.code)
        ).all()
        return tuple(self._record(universe) for universe in universes)

    def list_sync_runs(
        self,
        universe_id: int,
        *,
        offset: int,
        limit: int,
    ) -> UniverseSyncRunPage | None:
        universe = self._session.scalar(
            select(Universe)
            .where(Universe.id == universe_id)
        )
        if universe is None:
            return None
        condition = UniverseSyncRun.universe_code == universe.code
        total = self._session.scalar(
            select(func.count(UniverseSyncRun.id)).where(condition)
        ) or 0
        rows = self._session.scalars(
            select(UniverseSyncRun)
            .where(condition)
            .order_by(UniverseSyncRun.started_at.desc(), UniverseSyncRun.id.desc())
            .offset(offset)
            .limit(limit)
        ).all()
        return UniverseSyncRunPage(
            universe_id=universe.id,
            universe_code=universe.code,
            runs=tuple(UniverseSyncRunRecord(
                id=row.id,
                universe_code=row.universe_code,
                source=row.source,
                status=row.status,
                started_at=row.started_at,
                finished_at=row.finished_at,
                effective_date=row.effective_date,
                received_count=row.received_count,
                added_count=row.added_count,
                removed_count=row.removed_count,
                unchanged_count=row.unchanged_count,
                error=row.error,
            ) for row in rows),
            total=total,
            offset=offset,
            limit=limit,
        )

    @staticmethod
    def _record(universe: Universe) -> UniverseCatalogRecord:
        instruments = [membership.instrument for membership in universe.memberships]
        return UniverseCatalogRecord(
            id=universe.id,
            code=universe.code,
            name=universe.name,
            description=universe.description,
            source=universe.source,
            as_of=universe.as_of,
            fetched_at=universe.fetched_at,
            instrument_count=len(instruments),
            active_instrument_count=sum(
                instrument.is_active for instrument in instruments
            ),
            instrument_types=tuple(sorted({
                instrument.instrument_type for instrument in instruments
            })),
            venue_codes=tuple(sorted({
                instrument.venue.code
                for instrument in instruments
                if instrument.venue is not None
            })),
        )
