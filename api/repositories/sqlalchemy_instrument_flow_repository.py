"""SQLAlchemy persistence for canonical Instrument participant flows."""
from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import and_, case, delete, func, insert, or_, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from api.db.models import (
    Instrument,
    InstrumentFlowCoverage,
    InstrumentFlowObservation,
    Venue,
)
from api.instrument_symbols import canonical_symbol_expression
from api.repositories.instrument_flow_repository import (
    FlowInstrumentRecord,
    InstrumentFlowCoverageRecord,
    InstrumentFlowQuery,
    InstrumentFlowRecord,
    InstrumentFlowWriteRecord,
    ParticipantType,
)


_WRITE_BATCH_SIZE = 2_000


class SqlAlchemyInstrumentFlowRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_instrument(self, instrument_id: int) -> FlowInstrumentRecord | None:
        row = self._session.execute(
            select(
                Instrument.id,
                canonical_symbol_expression(),
                Instrument.instrument_type,
                Venue.code.label("venue_code"),
                Instrument.currency,
            )
            .outerjoin(Venue, Venue.id == Instrument.venue_id)
            .where(Instrument.id == instrument_id, Instrument.is_active.is_(True))
        ).one_or_none()
        if row is None:
            return None
        return FlowInstrumentRecord(
            instrument_id=row.id,
            symbol=row.symbol,
            instrument_type=row.instrument_type,
            venue_code=row.venue_code,
            currency=row.currency,
        )

    def get_coverage(
        self, instrument_id: int, participant_type: ParticipantType
    ) -> InstrumentFlowCoverageRecord | None:
        row = self._session.scalar(
            select(InstrumentFlowCoverage).where(
                InstrumentFlowCoverage.instrument_id == instrument_id,
                InstrumentFlowCoverage.participant_type == participant_type,
            )
        )
        if row is None:
            return None
        return InstrumentFlowCoverageRecord(
            instrument_id=row.instrument_id,
            participant_type=row.participant_type,
            first_date=row.first_date,
            last_date=row.last_date,
            row_count=int(row.row_count),
            source=row.source,
            fetched_at=row.fetched_at,
        )

    def iter_observations(
        self, query: InstrumentFlowQuery
    ) -> Iterable[InstrumentFlowRecord]:
        filters = [
            InstrumentFlowObservation.instrument_id == query.instrument_id,
            InstrumentFlowObservation.participant_type == query.participant_type,
        ]
        if query.start is not None:
            filters.append(InstrumentFlowObservation.trading_date >= query.start)
        if query.end is not None:
            filters.append(InstrumentFlowObservation.trading_date <= query.end)
        rows = self._session.scalars(
            select(InstrumentFlowObservation)
            .where(*filters)
            .order_by(InstrumentFlowObservation.trading_date)
        )
        for row in rows:
            yield InstrumentFlowRecord(
                instrument_id=row.instrument_id,
                trading_date=row.trading_date,
                participant_type=row.participant_type,
                buy_volume=row.buy_volume,
                buy_value=row.buy_value,
                sell_volume=row.sell_volume,
                sell_value=row.sell_value,
                net_volume=row.net_volume,
                net_value=row.net_value,
                currency=row.currency,
                source=row.source,
                fetched_at=row.fetched_at,
            )

    def upsert_observations(
        self, records: Iterable[InstrumentFlowWriteRecord]
    ) -> int:
        values = tuple(records)
        if not values:
            return 0
        instrument_ids = {record.instrument_id for record in values}
        existing_ids = set(self._session.scalars(
            select(Instrument.id).where(Instrument.id.in_(instrument_ids))
        ))
        missing = sorted(instrument_ids - existing_ids)
        if missing:
            raise ValueError(
                f"Instrument flows reference unknown instruments: {missing}"
            )
        rows = [self._write_values(record) for record in values]
        insert_factory = self._insert_factory()
        affected = 0
        for start in range(0, len(rows), _WRITE_BATCH_SIZE):
            batch = rows[start:start + _WRITE_BATCH_SIZE]
            statement = insert_factory(InstrumentFlowObservation).values(batch)
            excluded = statement.excluded
            statement = statement.on_conflict_do_update(
                index_elements=(
                    InstrumentFlowObservation.instrument_id,
                    InstrumentFlowObservation.trading_date,
                    InstrumentFlowObservation.participant_type,
                ),
                set_={
                    "buy_volume": excluded.buy_volume,
                    "buy_value": excluded.buy_value,
                    "sell_volume": excluded.sell_volume,
                    "sell_value": excluded.sell_value,
                    "net_volume": excluded.net_volume,
                    "net_value": excluded.net_value,
                    "currency": excluded.currency,
                    "source": excluded.source,
                    "fetched_at": excluded.fetched_at,
                    "updated_at": func.now(),
                },
                where=(
                    excluded.fetched_at
                    >= InstrumentFlowObservation.fetched_at
                ),
            )
            result = self._session.execute(statement)
            affected += (
                len(batch)
                if result.rowcount is None or result.rowcount < 0
                else int(result.rowcount)
            )
        self._rebuild_coverage({
            (record.instrument_id, record.participant_type) for record in values
        })
        return affected

    @staticmethod
    def _write_values(record: InstrumentFlowWriteRecord) -> dict[str, object]:
        return {
            "instrument_id": record.instrument_id,
            "trading_date": record.trading_date,
            "participant_type": record.participant_type,
            "buy_volume": record.buy_volume,
            "buy_value": record.buy_value,
            "sell_volume": record.sell_volume,
            "sell_value": record.sell_value,
            "net_volume": record.net_volume,
            "net_value": record.net_value,
            "currency": record.currency,
            "source": record.source,
            "fetched_at": record.fetched_at,
        }

    def _insert_factory(self):
        dialect = self._session.get_bind().dialect.name
        if dialect == "postgresql":
            return postgresql_insert
        if dialect == "sqlite":
            return sqlite_insert
        raise ValueError(f"Unsupported Instrument-flow write dialect: {dialect}")

    def _rebuild_coverage(
        self, keys: set[tuple[int, ParticipantType]]
    ) -> None:
        if not keys:
            return
        key_filter = or_(*(
            and_(
                InstrumentFlowObservation.instrument_id == instrument_id,
                InstrumentFlowObservation.participant_type == participant_type,
            )
            for instrument_id, participant_type in keys
        ))
        coverage_filter = or_(*(
            and_(
                InstrumentFlowCoverage.instrument_id == instrument_id,
                InstrumentFlowCoverage.participant_type == participant_type,
            )
            for instrument_id, participant_type in keys
        ))
        self._session.execute(
            delete(InstrumentFlowCoverage).where(coverage_filter)
        )
        aggregate = (
            select(
                InstrumentFlowObservation.instrument_id,
                InstrumentFlowObservation.participant_type,
                func.min(InstrumentFlowObservation.trading_date),
                func.max(InstrumentFlowObservation.trading_date),
                func.count(InstrumentFlowObservation.id),
                case(
                    (
                        func.count(func.distinct(InstrumentFlowObservation.source)) == 1,
                        func.min(InstrumentFlowObservation.source),
                    ),
                    else_="mixed",
                ),
                func.max(InstrumentFlowObservation.fetched_at),
            )
            .where(key_filter)
            .group_by(
                InstrumentFlowObservation.instrument_id,
                InstrumentFlowObservation.participant_type,
            )
        )
        self._session.execute(insert(InstrumentFlowCoverage).from_select(
            (
                "instrument_id", "participant_type", "first_date", "last_date",
                "row_count", "source", "fetched_at",
            ),
            aggregate,
        ))
