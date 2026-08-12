"""SQLAlchemy projection for canonical trading venues."""
from __future__ import annotations

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from api.db.models import Instrument, Venue
from api.repositories.venue_repository import VenueRecord, VenueRepository


class SqlAlchemyVenueRepository(VenueRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_venues(self) -> tuple[VenueRecord, ...]:
        rows = self._session.execute(
            select(
                Venue,
                func.count(Instrument.id),
                func.sum(case((Instrument.is_active.is_(True), 1), else_=0)),
            )
            .outerjoin(Instrument, Instrument.venue_id == Venue.id)
            .group_by(Venue.id)
            .order_by(Venue.venue_type, Venue.name, Venue.code)
        )
        return tuple(
            VenueRecord(
                id=venue.id,
                code=venue.code,
                name=venue.name,
                venue_type=venue.venue_type,
                country_code=venue.country_code,
                timezone_name=venue.timezone_name,
                trading_calendar_code=venue.trading_calendar_code,
                session_cutoff_time=venue.session_cutoff_time,
                is_active=venue.is_active,
                source=venue.source,
                instrument_count=int(instrument_count or 0),
                active_instrument_count=int(active_instrument_count or 0),
            )
            for venue, instrument_count, active_instrument_count in rows
        )
