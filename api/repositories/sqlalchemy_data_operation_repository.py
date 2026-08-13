"""SQLAlchemy scope projection for data-operation planning."""
from __future__ import annotations

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from api.db.models import (
    Instrument,
    FundamentalReport,
    PriceBarCoverage,
    PriceRefreshState,
    Universe,
    UniverseMembership,
    Venue,
    Watchlist,
    WatchlistMembership,
)
from api.repositories.data_operation_repository import (
    DataOperationInstrumentRecord,
    DataOperationScopeRecord,
    DataOperationScopeType,
)
from api.repositories.instrument_analysis_repository import (
    DEFAULT_CANONICAL_PRICE_BASIS,
    SPOT_PRICE_BASIS,
    US_EQUITY_PRICE_BASIS,
)


class SqlAlchemyDataOperationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_scope(
        self, scope_type: DataOperationScopeType, scope_id: str
    ) -> DataOperationScopeRecord | None:
        if scope_type == "universe":
            universe = self._session.execute(
                select(Universe.id, Universe.code, Universe.name).where(
                    Universe.code == scope_id.upper().strip()
                )
            ).one_or_none()
            if universe is None:
                return None
            rows = self._instrument_rows().join(
                UniverseMembership,
                UniverseMembership.instrument_id == Instrument.id,
            ).where(
                UniverseMembership.universe_id == universe.id,
                Instrument.is_active.is_(True),
            ).order_by(Instrument.ticker, Instrument.id)
            return DataOperationScopeRecord(
                scope_type="universe",
                scope_id=universe.code,
                name=universe.name,
                instruments=self._records(rows),
            )
        if scope_type == "watchlist":
            try:
                watchlist_id = int(scope_id)
            except ValueError:
                return None
            watchlist = self._session.execute(
                select(Watchlist.id, Watchlist.name).where(
                    Watchlist.id == watchlist_id
                )
            ).one_or_none()
            if watchlist is None:
                return None
            rows = self._instrument_rows().join(
                WatchlistMembership,
                WatchlistMembership.instrument_id == Instrument.id,
            ).where(
                WatchlistMembership.watchlist_id == watchlist.id,
                Instrument.is_active.is_(True),
            ).order_by(WatchlistMembership.position)
            return DataOperationScopeRecord(
                scope_type="watchlist",
                scope_id=str(watchlist.id),
                name=watchlist.name,
                instruments=self._records(rows),
            )
        try:
            instrument_id = int(scope_id)
        except ValueError:
            return None
        rows = self._instrument_rows().where(
            Instrument.id == instrument_id,
            Instrument.is_active.is_(True),
        )
        instruments = self._records(rows)
        if not instruments:
            return None
        instrument = instruments[0]
        return DataOperationScopeRecord(
            scope_type="instrument",
            scope_id=str(instrument.id),
            name=instrument.symbol,
            instruments=instruments,
        )

    @staticmethod
    def _instrument_rows():
        canonical_basis = case(
            (Instrument.instrument_type == "spot", SPOT_PRICE_BASIS),
            (
                Venue.code.in_((
                    "NASDAQ", "NYSE", "NYSE_AMERICAN", "NYSE_ARCA", "CBOE_BZX", "IEX",
                )),
                US_EQUITY_PRICE_BASIS,
            ),
            else_=DEFAULT_CANONICAL_PRICE_BASIS,
        )
        fundamental_coverage = (
            select(
                FundamentalReport.instrument_id,
                func.max(FundamentalReport.fetched_at).label(
                    "fundamental_fetched_at"
                ),
            )
            .group_by(FundamentalReport.instrument_id)
            .subquery()
        )
        return (
            select(
                Instrument.id,
                Instrument.ticker,
                Instrument.instrument_type,
                Instrument.company_id,
                Venue.code.label("venue_code"),
                canonical_basis.label("price_basis"),
                PriceBarCoverage.first_date,
                PriceBarCoverage.last_date,
                PriceBarCoverage.row_count,
                PriceBarCoverage.source.label("coverage_source"),
                PriceBarCoverage.fetched_at.label("coverage_fetched_at"),
                PriceRefreshState.attempted_through,
                PriceRefreshState.returned_through,
                PriceRefreshState.outcome.label("refresh_outcome"),
                PriceRefreshState.primary_source,
                PriceRefreshState.selected_source,
                PriceRefreshState.detail.label("refresh_detail"),
                PriceRefreshState.attempted_at,
                fundamental_coverage.c.fundamental_fetched_at,
            )
            .select_from(Instrument)
            .outerjoin(Venue, Venue.id == Instrument.venue_id)
            .outerjoin(
                PriceBarCoverage,
                (PriceBarCoverage.instrument_id == Instrument.id)
                & (PriceBarCoverage.price_basis == canonical_basis),
            )
            .outerjoin(
                PriceRefreshState,
                (PriceRefreshState.instrument_id == Instrument.id)
                & (PriceRefreshState.price_basis == canonical_basis),
            )
            .outerjoin(
                fundamental_coverage,
                fundamental_coverage.c.instrument_id == Instrument.id,
            )
        )

    def _records(self, statement) -> tuple[DataOperationInstrumentRecord, ...]:
        return tuple(
            DataOperationInstrumentRecord(
                id=row.id,
                symbol=row.ticker,
                instrument_type=row.instrument_type,
                company_id=row.company_id,
                venue_code=row.venue_code,
                price_basis=row.price_basis,
                first_date=row.first_date,
                last_date=row.last_date,
                row_count=int(row.row_count or 0),
                coverage_source=row.coverage_source,
                coverage_fetched_at=row.coverage_fetched_at,
                attempted_through=row.attempted_through,
                returned_through=row.returned_through,
                refresh_outcome=row.refresh_outcome,
                primary_source=row.primary_source,
                selected_source=row.selected_source,
                refresh_detail=row.refresh_detail,
                attempted_at=row.attempted_at,
                fundamental_fetched_at=row.fundamental_fetched_at,
            )
            for row in self._session.execute(statement)
        )
