"""SQLAlchemy persistence for normalized equity listing venues."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from api.db.models import Company, Instrument, Venue
from api.equity_venues import (
    EQUITY_VENUES,
    EQUITY_VENUE_SOURCE,
)
from api.repositories.equity_venue_repository import (
    EquityVenueAssignment,
    EquityVenueInstrumentRecord,
    EquityVenueRepository,
)
from api.venue_calendars import venue_calendar


class SqlAlchemyEquityVenueRepository(EquityVenueRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def ensure_venue_registry(self) -> None:
        codes = {row.code for row in EQUITY_VENUES}
        venues = {
            row.code: row
            for row in self._session.scalars(
                select(Venue).where(Venue.code.in_(codes))
            )
        }
        for definition in EQUITY_VENUES:
            schedule = venue_calendar(definition.code)
            venue = venues.get(definition.code)
            if venue is None:
                venue = Venue(code=definition.code)
                self._session.add(venue)
            venue.name = definition.name
            venue.venue_type = definition.venue_type
            venue.country_code = definition.country_code
            venue.timezone_name = schedule.timezone_name
            venue.trading_calendar_code = schedule.trading_calendar_code
            venue.session_cutoff_time = schedule.session_cutoff_time
            venue.is_active = True
            venue.source = EQUITY_VENUE_SOURCE

    def list_us_equity_instruments(
        self,
    ) -> tuple[EquityVenueInstrumentRecord, ...]:
        rows = self._session.scalars(
            select(Instrument)
            .where(
                Instrument.company_id.is_not(None),
                Instrument.instrument_type == "common_stock",
                Instrument.company.has(Company.country_code == "US"),
                Instrument.is_active.is_(True),
            )
            .options(
                selectinload(Instrument.symbols),
                selectinload(Instrument.venue),
            )
            .order_by(Instrument.ticker, Instrument.id)
        )
        return tuple(
            EquityVenueInstrumentRecord(
                instrument_id=row.id,
                symbol=row.ticker,
                symbol_aliases=tuple(
                    symbol.symbol
                    for symbol in row.symbols
                    if symbol.valid_to is None
                ),
                venue_code=row.venue.code if row.venue else None,
            )
            for row in rows
        )

    def assign_venues(
        self,
        assignments: tuple[EquityVenueAssignment, ...],
    ) -> int:
        if not assignments:
            return 0
        instrument_ids = {row.instrument_id for row in assignments}
        venue_codes = {row.venue_code for row in assignments}
        instruments = {
            row.id: row
            for row in self._session.scalars(
                select(Instrument).where(Instrument.id.in_(instrument_ids))
            )
        }
        venues = {
            row.code: row
            for row in self._session.scalars(
                select(Venue).where(Venue.code.in_(venue_codes))
            )
        }
        updated = 0
        for assignment in assignments:
            instrument = instruments[assignment.instrument_id]
            venue = venues[assignment.venue_code]
            if instrument.venue_id != venue.id:
                updated += 1
            instrument.venue = venue
        return updated
