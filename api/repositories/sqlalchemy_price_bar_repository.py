"""SQLAlchemy implementation of the price-bar repository."""
from __future__ import annotations

from collections.abc import Iterable
from datetime import date

from sqlalchemy import case, delete, func, insert, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from api.db.models import (
    Instrument,
    PriceBar,
    PriceBarCoverage,
    PriceRefreshState,
    Venue,
)
from api.repositories.price_bar_repository import (
    PriceBarRecord,
    PriceInstrumentRecord,
    PriceRefreshStateRecord,
    PriceRefreshStateWriteRecord,
    InstrumentPriceBarQuery,
    InstrumentSetPriceBarQuery,
    SymbolPriceCoverageRecord,
    PriceBarWriteRecord,
)


_WRITE_BATCH_SIZE = 2_000


class SqlAlchemyPriceBarRepository:
    def __init__(self, session: Session):
        self._session = session

    def get_instrument(self, instrument_id: int) -> PriceInstrumentRecord | None:
        row = self._session.execute(
            select(
                Instrument.id,
                Instrument.ticker,
                Instrument.currency,
                Instrument.instrument_type,
                Venue.code.label("venue_code"),
            )
            .outerjoin(Venue, Venue.id == Instrument.venue_id)
            .where(Instrument.id == instrument_id, Instrument.is_active.is_(True))
        ).one_or_none()
        if row is None:
            return None
        return PriceInstrumentRecord(
            instrument_id=row.id,
            ticker=row.ticker,
            currency=row.currency,
            instrument_type=row.instrument_type,
            venue_code=row.venue_code,
        )

    def get_instrument_coverage(
        self, instrument_id: int, price_basis: str
    ) -> SymbolPriceCoverageRecord | None:
        rows = self.list_instrument_coverages((instrument_id,), price_basis)
        return rows[0] if rows else None

    def list_instrument_coverages(
        self, instrument_ids: tuple[int, ...], price_basis: str
    ) -> tuple[SymbolPriceCoverageRecord, ...]:
        if not instrument_ids:
            return ()
        rows = self._session.execute(
            select(Instrument.id, Instrument.ticker, PriceBarCoverage)
            .join(PriceBarCoverage, PriceBarCoverage.instrument_id == Instrument.id)
            .where(
                Instrument.id.in_(instrument_ids),
                Instrument.is_active.is_(True),
                PriceBarCoverage.price_basis == price_basis,
            )
            .order_by(Instrument.id)
        )
        return tuple(
            SymbolPriceCoverageRecord(
                instrument_id=instrument_id,
                ticker=ticker,
                first_date=coverage.first_date,
                last_date=coverage.last_date,
                row_count=int(coverage.row_count),
                source=coverage.source,
                fetched_at=coverage.fetched_at,
            )
            for instrument_id, ticker, coverage in rows
        )

    def list_instrument_refresh_states(
        self, instrument_ids: tuple[int, ...], price_basis: str
    ) -> tuple[PriceRefreshStateRecord, ...]:
        if not instrument_ids:
            return ()
        rows = self._session.execute(
            select(Instrument.id, Instrument.ticker, PriceRefreshState)
            .join(PriceRefreshState, PriceRefreshState.instrument_id == Instrument.id)
            .where(
                Instrument.id.in_(instrument_ids),
                Instrument.is_active.is_(True),
                PriceRefreshState.price_basis == price_basis,
            )
            .order_by(Instrument.id)
        )
        return tuple(
            PriceRefreshStateRecord(
                instrument_id=instrument_id,
                ticker=ticker,
                price_basis=state.price_basis,
                attempted_through=state.attempted_through,
                returned_through=state.returned_through,
                outcome=state.outcome,
                primary_source=state.primary_source,
                selected_source=state.selected_source,
                detail=state.detail,
                attempted_at=state.attempted_at,
            )
            for instrument_id, ticker, state in rows
        )

    def upsert_bars(self, records: Iterable[PriceBarWriteRecord]) -> int:
        values = tuple(records)
        if not values:
            return 0
        instrument_ids = {record.instrument_id for record in values}
        existing_ids = set(self._session.scalars(
            select(Instrument.id).where(Instrument.id.in_(instrument_ids))
        ))
        missing = sorted(instrument_ids - existing_ids)
        if missing:
            raise ValueError(f"Price bars reference unknown instruments: {missing}")

        rows = [
            {
                "instrument_id": record.instrument_id,
                "trading_date": record.trading_date,
                "open": record.open,
                "high": record.high,
                "low": record.low,
                "close": record.close,
                "volume": record.volume,
                "currency": record.currency,
                "price_scale": record.price_scale,
                "price_basis": record.price_basis,
                "source": record.source,
                "fetched_at": record.fetched_at,
            }
            for record in values
        ]
        dialect = self._session.get_bind().dialect.name
        if dialect == "postgresql":
            insert_factory = postgresql_insert
        elif dialect == "sqlite":
            insert_factory = sqlite_insert
        else:
            raise ValueError(f"Unsupported price-bar write dialect: {dialect}")

        affected = 0
        for start in range(0, len(rows), _WRITE_BATCH_SIZE):
            batch = rows[start:start + _WRITE_BATCH_SIZE]
            statement = insert_factory(PriceBar).values(
                batch
            )
            statement = statement.on_conflict_do_update(
                index_elements=(
                    PriceBar.instrument_id,
                    PriceBar.trading_date,
                    PriceBar.price_basis,
                ),
                set_={
                    "open": statement.excluded.open,
                    "high": statement.excluded.high,
                    "low": statement.excluded.low,
                    "close": statement.excluded.close,
                    "volume": statement.excluded.volume,
                    "currency": statement.excluded.currency,
                    "price_scale": statement.excluded.price_scale,
                    "source": statement.excluded.source,
                    "fetched_at": statement.excluded.fetched_at,
                    "updated_at": func.now(),
                },
                where=statement.excluded.fetched_at >= PriceBar.fetched_at,
            )
            result = self._session.execute(statement)
            affected += (
                len(batch)
                if result.rowcount is None or result.rowcount < 0
                else int(result.rowcount)
            )
        self._rebuild_coverage(instrument_ids)
        return affected

    def upsert_refresh_states(
        self, records: Iterable[PriceRefreshStateWriteRecord]
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
            raise ValueError(f"Refresh states reference unknown instruments: {missing}")
        rows = [
            {
                "instrument_id": record.instrument_id,
                "price_basis": record.price_basis,
                "attempted_through": record.attempted_through,
                "returned_through": record.returned_through,
                "outcome": record.outcome,
                "primary_source": record.primary_source,
                "selected_source": record.selected_source,
                "detail": record.detail,
                "attempted_at": record.attempted_at,
            }
            for record in values
        ]
        dialect = self._session.get_bind().dialect.name
        if dialect == "postgresql":
            insert_factory = postgresql_insert
        elif dialect == "sqlite":
            insert_factory = sqlite_insert
        else:
            raise ValueError(f"Unsupported refresh-state dialect: {dialect}")
        statement = insert_factory(PriceRefreshState).values(rows)
        statement = statement.on_conflict_do_update(
            index_elements=(
                PriceRefreshState.instrument_id,
                PriceRefreshState.price_basis,
            ),
            set_={
                "attempted_through": statement.excluded.attempted_through,
                "returned_through": statement.excluded.returned_through,
                "outcome": statement.excluded.outcome,
                "primary_source": statement.excluded.primary_source,
                "selected_source": statement.excluded.selected_source,
                "detail": statement.excluded.detail,
                "attempted_at": statement.excluded.attempted_at,
                "updated_at": func.now(),
            },
            where=statement.excluded.attempted_at >= PriceRefreshState.attempted_at,
        )
        result = self._session.execute(statement)
        return (
            len(rows)
            if result.rowcount is None or result.rowcount < 0
            else int(result.rowcount)
        )

    def _rebuild_coverage(self, instrument_ids: set[int]) -> None:
        if not instrument_ids:
            return
        self._session.execute(
            delete(PriceBarCoverage).where(
                PriceBarCoverage.instrument_id.in_(instrument_ids)
            )
        )
        columns = (
            "instrument_id",
            "price_basis",
            "first_date",
            "last_date",
            "row_count",
            "source",
            "fetched_at",
        )
        aggregate = (
            select(
                PriceBar.instrument_id,
                PriceBar.price_basis,
                func.min(PriceBar.trading_date),
                func.max(PriceBar.trading_date),
                func.count(PriceBar.id),
                case(
                    (func.count(func.distinct(PriceBar.source)) == 1, func.min(PriceBar.source)),
                    else_="mixed",
                ),
                func.max(PriceBar.fetched_at),
            )
            .where(PriceBar.instrument_id.in_(instrument_ids))
            .group_by(PriceBar.instrument_id, PriceBar.price_basis)
        )
        self._session.execute(
            insert(PriceBarCoverage).from_select(columns, aggregate)
        )

    def iter_instrument_bars(
        self, query: InstrumentPriceBarQuery
    ) -> Iterable[PriceBarRecord]:
        filters = [
            Instrument.id == query.instrument_id,
            Instrument.is_active.is_(True),
            PriceBar.price_basis == query.price_basis,
        ]
        if query.start:
            filters.append(PriceBar.trading_date >= query.start)
        if query.end:
            filters.append(PriceBar.trading_date <= query.end)
        statement = (
            select(
                Instrument.ticker,
                PriceBar.trading_date,
                PriceBar.open,
                PriceBar.high,
                PriceBar.low,
                PriceBar.close,
                PriceBar.volume,
                PriceBar.currency,
                PriceBar.price_scale,
                PriceBar.price_basis,
                PriceBar.source,
                PriceBar.fetched_at,
            )
            .join(PriceBar, PriceBar.instrument_id == Instrument.id)
            .where(*filters)
            .order_by(PriceBar.trading_date)
            .execution_options(yield_per=5_000)
        )
        for row in self._session.execute(statement):
            yield PriceBarRecord(
                ticker=row.ticker,
                trading_date=row.trading_date,
                open=float(row.open),
                high=float(row.high),
                low=float(row.low),
                close=float(row.close),
                volume=float(row.volume) if row.volume is not None else None,
                currency=row.currency,
                price_scale=row.price_scale,
                price_basis=row.price_basis,
                source=row.source,
                fetched_at=row.fetched_at,
            )

    def iter_instrument_set_bars(
        self, query: InstrumentSetPriceBarQuery
    ) -> Iterable[PriceBarRecord]:
        if not query.instrument_ids:
            return
        filters = [
            Instrument.id.in_(query.instrument_ids),
            Instrument.is_active.is_(True),
            PriceBar.price_basis == query.price_basis,
        ]
        if query.start:
            filters.append(PriceBar.trading_date >= query.start)
        if query.end:
            filters.append(PriceBar.trading_date <= query.end)
        statement = (
            select(
                Instrument.ticker,
                PriceBar.trading_date,
                PriceBar.open,
                PriceBar.high,
                PriceBar.low,
                PriceBar.close,
                PriceBar.volume,
                PriceBar.currency,
                PriceBar.price_scale,
                PriceBar.price_basis,
                PriceBar.source,
                PriceBar.fetched_at,
            )
            .join(PriceBar, PriceBar.instrument_id == Instrument.id)
            .where(*filters)
            .order_by(Instrument.id, PriceBar.trading_date)
            .execution_options(yield_per=5_000)
        )
        for row in self._session.execute(statement):
            yield PriceBarRecord(
                ticker=row.ticker,
                trading_date=row.trading_date,
                open=float(row.open),
                high=float(row.high),
                low=float(row.low),
                close=float(row.close),
                volume=float(row.volume) if row.volume is not None else None,
                currency=row.currency,
                price_scale=row.price_scale,
                price_basis=row.price_basis,
                source=row.source,
                fetched_at=row.fetched_at,
            )
