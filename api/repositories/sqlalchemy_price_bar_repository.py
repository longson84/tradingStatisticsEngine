"""SQLAlchemy implementation of the price-bar repository."""
from __future__ import annotations

from collections.abc import Iterable
from datetime import date

from sqlalchemy import delete, func, insert, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from api.db.models import (
    Instrument,
    PriceBar,
    PriceBarCoverage,
    Universe,
    UniverseMembership,
)
from api.repositories.price_bar_repository import (
    PriceBarCoverageRecord,
    PriceBarQuery,
    PriceBarRecord,
    PriceBarStatusRecord,
    PriceBarWriteRecord,
)


_WRITE_BATCH_SIZE = 2_000


class SqlAlchemyPriceBarRepository:
    def __init__(self, session: Session):
        self._session = session

    def get_universe_market(self, universe: str) -> str | None:
        return self._session.scalar(
            select(Universe.market).where(Universe.code == universe)
        )

    def get_latest_date(self, universe: str, price_basis: str) -> date | None:
        return self._session.scalar(
            select(func.max(PriceBar.trading_date))
            .select_from(PriceBar)
            .join(Instrument, Instrument.id == PriceBar.instrument_id)
            .join(
                UniverseMembership,
                UniverseMembership.instrument_id == Instrument.id,
            )
            .join(Universe, Universe.id == UniverseMembership.universe_id)
            .where(
                Universe.code == universe,
                PriceBar.price_basis == price_basis,
            )
        )

    def list_coverage(
        self, universe: str, price_basis: str
    ) -> tuple[PriceBarCoverageRecord, ...]:
        rows = self._session.execute(
            select(
                Instrument.ticker,
                PriceBarCoverage.first_date,
                PriceBarCoverage.last_date,
            )
            .select_from(PriceBarCoverage)
            .join(Instrument, Instrument.id == PriceBarCoverage.instrument_id)
            .join(
                UniverseMembership,
                UniverseMembership.instrument_id == Instrument.id,
            )
            .join(Universe, Universe.id == UniverseMembership.universe_id)
            .where(
                Universe.code == universe,
                PriceBarCoverage.price_basis == price_basis,
            )
            .order_by(Instrument.ticker)
        )
        return tuple(
            PriceBarCoverageRecord(
                ticker=ticker,
                first_date=first_date,
                last_date=last_date,
            )
            for ticker, first_date, last_date in rows
        )

    def get_status(
        self, universe: str, price_basis: str
    ) -> PriceBarStatusRecord | None:
        summary = self._session.execute(
            select(
                Universe.market,
                func.max(PriceBarCoverage.fetched_at),
                func.min(PriceBarCoverage.first_date),
                func.max(PriceBarCoverage.last_date),
                func.count(func.distinct(Instrument.id)),
                func.sum(PriceBarCoverage.row_count),
            )
            .select_from(PriceBarCoverage)
            .join(Instrument, Instrument.id == PriceBarCoverage.instrument_id)
            .join(
                UniverseMembership,
                UniverseMembership.instrument_id == Instrument.id,
            )
            .join(Universe, Universe.id == UniverseMembership.universe_id)
            .where(
                Universe.code == universe,
                PriceBarCoverage.price_basis == price_basis,
            )
            .group_by(Universe.market)
        ).one_or_none()
        if summary is None:
            return None
        sources = tuple(self._session.scalars(
            select(PriceBarCoverage.source)
            .select_from(PriceBarCoverage)
            .join(Instrument, Instrument.id == PriceBarCoverage.instrument_id)
            .join(
                UniverseMembership,
                UniverseMembership.instrument_id == Instrument.id,
            )
            .join(Universe, Universe.id == UniverseMembership.universe_id)
            .where(
                Universe.code == universe,
                PriceBarCoverage.price_basis == price_basis,
            )
            .distinct()
            .order_by(PriceBarCoverage.source)
        ))
        return PriceBarStatusRecord(
            universe=universe,
            market=summary[0],
            fetched_at=summary[1],
            first_date=summary[2],
            last_date=summary[3],
            symbol_count=int(summary[4]),
            row_count=int(summary[5]),
            sources=sources,
            price_basis=price_basis,
        )

    def list_market_universes(self, market: str) -> tuple[str, ...]:
        return tuple(self._session.scalars(
            select(Universe.code)
            .where(Universe.market == market)
            .order_by(Universe.code)
        ))

    def delete_market_bars(self, market: str) -> int:
        instrument_ids = select(Instrument.id).where(Instrument.market == market)
        self._session.execute(
            delete(PriceBarCoverage).where(
                PriceBarCoverage.instrument_id.in_(instrument_ids)
            )
        )
        result = self._session.execute(
            delete(PriceBar).where(PriceBar.instrument_id.in_(instrument_ids))
        )
        return max(0, int(result.rowcount or 0))

    def upsert_bars(self, records: Iterable[PriceBarWriteRecord]) -> int:
        values = tuple(records)
        if not values:
            return 0
        instrument_keys = {(record.market, record.ticker) for record in values}
        markets = {market for market, _ in instrument_keys}
        tickers = {ticker for _, ticker in instrument_keys}
        instrument_ids = {
            (market, ticker): instrument_id
            for market, ticker, instrument_id in self._session.execute(
                select(Instrument.market, Instrument.ticker, Instrument.id).where(
                    Instrument.market.in_(markets),
                    Instrument.ticker.in_(tickers),
                )
            )
        }
        missing = sorted(instrument_keys - set(instrument_ids))
        if missing:
            raise ValueError(f"Price bars reference unknown instruments: {missing}")

        rows = [
            {
                "instrument_id": instrument_ids[(record.market, record.ticker)],
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
        self._rebuild_coverage(set(instrument_ids.values()))
        return affected

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
                func.min(PriceBar.source),
                func.max(PriceBar.fetched_at),
            )
            .where(PriceBar.instrument_id.in_(instrument_ids))
            .group_by(PriceBar.instrument_id, PriceBar.price_basis)
        )
        self._session.execute(
            insert(PriceBarCoverage).from_select(columns, aggregate)
        )

    def iter_bars(self, query: PriceBarQuery) -> Iterable[PriceBarRecord]:
        filters = [
            Universe.code == query.universe,
            PriceBar.price_basis == query.price_basis,
        ]
        if query.ticker:
            filters.append(Instrument.ticker == query.ticker)
        if query.start:
            filters.append(PriceBar.trading_date >= query.start)
        if query.end:
            filters.append(PriceBar.trading_date <= query.end)

        statement = (
            select(
                Instrument.ticker,
                Instrument.market,
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
            .join(
                UniverseMembership,
                UniverseMembership.instrument_id == Instrument.id,
            )
            .join(Universe, Universe.id == UniverseMembership.universe_id)
            .where(*filters)
            .order_by(Instrument.ticker, PriceBar.trading_date)
            .execution_options(yield_per=5_000)
        )
        for row in self._session.execute(statement):
            yield PriceBarRecord(
                ticker=row.ticker,
                market=row.market,
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
