"""SQLAlchemy implementation of the price-bar repository."""
from __future__ import annotations

from collections.abc import Iterable
from datetime import date

import pandas as pd
from sqlalchemy import case, delete, func, insert, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from api.db.models import (
    Instrument,
    PriceBar,
    PriceBarCoverage,
    PriceRefreshState,
    Universe,
    UniverseMembership,
)
from api.repositories.price_bar_repository import (
    PriceBarCoverageRecord,
    PriceBarQuery,
    PriceBarRecord,
    PriceRefreshStateRecord,
    PriceRefreshStateWriteRecord,
    SymbolPriceBarQuery,
    SymbolSetPriceBarQuery,
    SymbolPriceCoverageRecord,
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

    def instrument_exists(self, market: str, ticker: str) -> bool:
        return self._session.scalar(
            select(Instrument.id).where(
                Instrument.market == market,
                Instrument.ticker == ticker,
                Instrument.is_active.is_(True),
            )
        ) is not None

    def get_symbol_coverage(
        self, market: str, ticker: str, price_basis: str
    ) -> SymbolPriceCoverageRecord | None:
        row = self._session.execute(
            select(Instrument.ticker, Instrument.market, PriceBarCoverage)
            .join(
                PriceBarCoverage,
                PriceBarCoverage.instrument_id == Instrument.id,
            )
            .where(
                Instrument.market == market,
                Instrument.ticker == ticker,
                Instrument.is_active.is_(True),
                PriceBarCoverage.price_basis == price_basis,
            )
        ).one_or_none()
        if row is None:
            return None
        stored_ticker, stored_market, coverage = row
        return SymbolPriceCoverageRecord(
            ticker=stored_ticker,
            market=stored_market,
            first_date=coverage.first_date,
            last_date=coverage.last_date,
            row_count=int(coverage.row_count),
            source=coverage.source,
            fetched_at=coverage.fetched_at,
        )

    def list_symbol_coverages(
        self, market: str, tickers: tuple[str, ...], price_basis: str
    ) -> tuple[SymbolPriceCoverageRecord, ...]:
        if not tickers:
            return ()
        rows = self._session.execute(
            select(Instrument.ticker, Instrument.market, PriceBarCoverage)
            .join(
                PriceBarCoverage,
                PriceBarCoverage.instrument_id == Instrument.id,
            )
            .where(
                Instrument.market == market,
                Instrument.ticker.in_(tickers),
                Instrument.is_active.is_(True),
                PriceBarCoverage.price_basis == price_basis,
            )
            .order_by(Instrument.ticker)
        )
        return tuple(
            SymbolPriceCoverageRecord(
                ticker=ticker,
                market=stored_market,
                first_date=coverage.first_date,
                last_date=coverage.last_date,
                row_count=int(coverage.row_count),
                source=coverage.source,
                fetched_at=coverage.fetched_at,
            )
            for ticker, stored_market, coverage in rows
        )

    def list_refresh_states(
        self, market: str, tickers: tuple[str, ...], price_basis: str
    ) -> tuple[PriceRefreshStateRecord, ...]:
        if not tickers:
            return ()
        rows = self._session.execute(
            select(Instrument.ticker, Instrument.market, PriceRefreshState)
            .join(
                PriceRefreshState,
                PriceRefreshState.instrument_id == Instrument.id,
            )
            .where(
                Instrument.market == market,
                Instrument.ticker.in_(tickers),
                Instrument.is_active.is_(True),
                PriceRefreshState.price_basis == price_basis,
            )
            .order_by(Instrument.ticker)
        )
        return tuple(
            PriceRefreshStateRecord(
                ticker=ticker,
                market=stored_market,
                price_basis=state.price_basis,
                attempted_through=state.attempted_through,
                returned_through=state.returned_through,
                outcome=state.outcome,
                primary_source=state.primary_source,
                selected_source=state.selected_source,
                detail=state.detail,
                attempted_at=state.attempted_at,
            )
            for ticker, stored_market, state in rows
        )

    def get_latest_date(self, universe: str, price_basis: str) -> date | None:
        return self._session.scalar(
            select(func.max(PriceBarCoverage.last_date))
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
        )

    def load_close_matrix(self, query: PriceBarQuery) -> pd.DataFrame:
        filters = [
            Universe.code == query.universe,
            PriceBar.price_basis == query.price_basis,
        ]
        if query.start:
            filters.append(PriceBar.trading_date >= query.start)
        if query.end:
            filters.append(PriceBar.trading_date <= query.end)

        members = dict(self._session.execute(
            select(Instrument.id, Instrument.ticker)
            .join(
                UniverseMembership,
                UniverseMembership.instrument_id == Instrument.id,
            )
            .join(Universe, Universe.id == UniverseMembership.universe_id)
            .where(Universe.code == query.universe)
        ).all())
        statement = (
            select(
                PriceBar.instrument_id,
                PriceBar.trading_date.label("date"),
                PriceBar.close,
            )
            .join(Instrument, Instrument.id == PriceBar.instrument_id)
            .join(
                UniverseMembership,
                UniverseMembership.instrument_id == Instrument.id,
            )
            .join(Universe, Universe.id == UniverseMembership.universe_id)
            .where(*filters)
            .order_by(PriceBar.instrument_id, PriceBar.trading_date)
        )
        rows = pd.read_sql_query(statement, self._session.connection())
        if rows.empty:
            return pd.DataFrame()
        rows["date"] = pd.to_datetime(rows["date"])
        matrix = rows.pivot(
            index="date", columns="instrument_id", values="close"
        )
        matrix = matrix.rename(columns=members).sort_index()
        matrix.columns.name = None
        return matrix.astype(float)

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
        self, universe: str, price_basis: str, expected_session: date
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
        coverages = self.list_coverage(universe, price_basis)
        all_member_tickers = tuple(self._session.scalars(
            select(Instrument.ticker)
            .select_from(UniverseMembership)
            .join(Instrument, Instrument.id == UniverseMembership.instrument_id)
            .join(Universe, Universe.id == UniverseMembership.universe_id)
            .where(Universe.code == universe)
            .order_by(Instrument.ticker)
        ))
        universe_symbol_count = len(all_member_tickers)
        current_tickers = {
            row.ticker for row in coverages if row.last_date >= expected_session
        }
        refresh_states = self.list_refresh_states(
            summary[0], all_member_tickers, price_basis
        )
        checked_no_new_tickers = {
            row.ticker
            for row in refresh_states
            if row.ticker not in current_tickers
            and row.attempted_through >= expected_session
            and row.outcome == "checked_no_new_bar"
        }
        failed_refresh_symbol_count = sum(
            row.attempted_through >= expected_session and row.outcome == "failed"
            for row in refresh_states
        )
        current_symbol_count = len(current_tickers)
        stale_symbol_count = max(
            0,
            len(coverages) - current_symbol_count - len(checked_no_new_tickers),
        )
        missing_symbol_count = max(0, universe_symbol_count - len(coverages))
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
            expected_session=expected_session,
            coverage_through=min(row.last_date for row in coverages),
            universe_symbol_count=universe_symbol_count,
            current_symbol_count=current_symbol_count,
            stale_symbol_count=stale_symbol_count,
            missing_symbol_count=missing_symbol_count,
            checked_no_new_bar_count=len(checked_no_new_tickers),
            failed_refresh_symbol_count=failed_refresh_symbol_count,
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

    def upsert_refresh_states(
        self, records: Iterable[PriceRefreshStateWriteRecord]
    ) -> int:
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
            raise ValueError(f"Refresh states reference unknown instruments: {missing}")
        rows = [
            {
                "instrument_id": instrument_ids[(record.market, record.ticker)],
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

    def iter_symbol_bars(
        self, query: SymbolPriceBarQuery
    ) -> Iterable[PriceBarRecord]:
        filters = [
            Instrument.market == query.market,
            Instrument.ticker == query.ticker,
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
            .where(*filters)
            .order_by(PriceBar.trading_date)
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

    def iter_symbol_set_bars(
        self, query: SymbolSetPriceBarQuery
    ) -> Iterable[PriceBarRecord]:
        if not query.tickers:
            return
        filters = [
            Instrument.market == query.market,
            Instrument.ticker.in_(query.tickers),
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
