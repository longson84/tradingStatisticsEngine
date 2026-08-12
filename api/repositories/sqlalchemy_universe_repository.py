"""SQLAlchemy projection for canonical instrument universes."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from api.db.models import Instrument, Universe, UniverseMembership
from api.repositories.universe_repository import UniverseCatalogRecord


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
