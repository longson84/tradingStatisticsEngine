"""SQLAlchemy projection of instrument, venue, and provider-symbol routing data."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.db.models import Instrument, InstrumentSymbol, Venue
from api.instrument_data_routing import InstrumentRoutingMetadata, ProviderSymbol


class SqlAlchemyInstrumentRoutingRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def find_instrument_route_metadata(
        self, namespace: str, symbol: str
    ) -> InstrumentRoutingMetadata | None:
        instrument_ids = tuple(self._session.scalars(
            select(InstrumentSymbol.instrument_id).where(
                InstrumentSymbol.namespace == namespace,
                InstrumentSymbol.symbol == symbol.upper().strip(),
                InstrumentSymbol.valid_to.is_(None),
                InstrumentSymbol.is_primary.is_(True),
            )
        ))
        if len(instrument_ids) != 1:
            return None
        return self.get_instrument_route_metadata(instrument_ids[0])

    def get_instrument_route_metadata(
        self, instrument_id: int
    ) -> InstrumentRoutingMetadata | None:
        rows = self.get_instrument_routes_metadata((instrument_id,))
        return rows[0] if rows else None

    def get_instrument_routes_metadata(
        self, instrument_ids: tuple[int, ...]
    ) -> tuple[InstrumentRoutingMetadata, ...]:
        if not instrument_ids:
            return ()
        instruments = tuple(self._session.execute(
            select(
                Instrument.id,
                Instrument.ticker,
                Instrument.instrument_type,
                Instrument.company_id,
                Instrument.currency,
                Instrument.source,
                Venue.code.label("venue_code"),
                Venue.timezone_name,
                Venue.trading_calendar_code,
                Venue.session_cutoff_time,
            )
            .outerjoin(Venue, Venue.id == Instrument.venue_id)
            .where(
                Instrument.id.in_(instrument_ids),
                Instrument.is_active.is_(True),
            )
            .order_by(Instrument.id)
        ))
        symbols: dict[int, list[ProviderSymbol]] = {}
        for instrument_id, namespace, symbol in self._session.execute(
            select(
                InstrumentSymbol.instrument_id,
                InstrumentSymbol.namespace,
                InstrumentSymbol.symbol,
            )
            .where(
                InstrumentSymbol.instrument_id.in_(instrument_ids),
                InstrumentSymbol.valid_to.is_(None),
                InstrumentSymbol.is_primary.is_(True),
            )
            .order_by(InstrumentSymbol.instrument_id, InstrumentSymbol.namespace)
        ):
            symbols.setdefault(instrument_id, []).append(
                ProviderSymbol(namespace=namespace, symbol=symbol)
            )
        return tuple(
            InstrumentRoutingMetadata(
                instrument_id=row.id,
                canonical_symbol=row.ticker,
                instrument_type=row.instrument_type,
                company_id=row.company_id,
                venue_code=row.venue_code,
                currency=row.currency,
                catalog_source=row.source,
                provider_symbols=tuple(symbols.get(row.id, ())),
                timezone_name=row.timezone_name,
                trading_calendar_code=row.trading_calendar_code,
                session_cutoff_time=row.session_cutoff_time,
            )
            for row in instruments
        )
