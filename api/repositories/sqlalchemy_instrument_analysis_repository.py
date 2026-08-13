"""SQLAlchemy projection for analysis-ready instruments and their price bars."""
from __future__ import annotations

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session, aliased

from api.db.models import (
    Asset,
    Company,
    Instrument,
    PriceBar,
    PriceBarCoverage,
    Universe,
    UniverseMembership,
    Venue,
)
from api.repositories.instrument_analysis_repository import (
    AnalysisInstrumentListResult,
    AnalysisInstrumentFacetCount,
    AnalysisInstrumentFacets,
    AnalysisInstrumentPriceBarRecord,
    AnalysisInstrumentQuery,
    AnalysisInstrumentRecord,
    DEFAULT_CANONICAL_PRICE_BASIS,
    MARKET_INDEX_PRICE_BASIS,
    SPOT_PRICE_BASIS,
    US_EQUITY_PRICE_BASIS,
)
from api.repositories.price_bar_repository import PriceBarRecord
from api.instrument_symbols import canonical_symbol_expression


class SqlAlchemyInstrumentAnalysisRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_instruments(
        self, query: AnalysisInstrumentQuery
    ) -> AnalysisInstrumentListResult:
        statement, filters = self._statement(
            query.scope,
            query.search,
            query.universe,
            query.sector,
            query.industry,
            query.venue_code,
        )
        if query.has_price_history:
            filters.append(PriceBarCoverage.instrument_id.is_not(None))

        total = int(self._session.scalar(
            statement.with_only_columns(func.count(Instrument.id)).where(*filters)
        ) or 0)
        rows = tuple(self._session.execute(
            statement.where(*filters)
            .order_by(canonical_symbol_expression(), Venue.code, Instrument.id)
            .offset(query.offset)
            .limit(query.limit)
        ))
        facet_statement, facet_filters = self._statement(
            query.scope,
            query.search,
            query.universe,
            None,
            query.industry,
            query.venue_code,
        )
        if query.has_price_history:
            facet_filters.append(PriceBarCoverage.instrument_id.is_not(None))
        all_count = int(self._session.scalar(
            facet_statement.with_only_columns(func.count(Instrument.id)).where(
                *facet_filters
            )
        ) or 0)
        sector_value = func.coalesce(Company.sector, "Unknown")
        sector_rows = self._session.execute(
            facet_statement.with_only_columns(
                sector_value,
                func.count(Instrument.id),
            )
            .where(*facet_filters)
            .group_by(sector_value)
            .order_by(sector_value)
        )
        return AnalysisInstrumentListResult(
            rows=self._records(rows),
            total=total,
            facets=AnalysisInstrumentFacets(
                all_count=all_count,
                sectors=tuple(
                    AnalysisInstrumentFacetCount(value=value, count=int(count))
                    for value, count in sector_rows
                ),
            ),
        )

    def get_instrument(self, instrument_id: int) -> AnalysisInstrumentRecord | None:
        statement, filters = self._statement(None, None, None)
        row = self._session.execute(
            statement.where(*filters, Instrument.id == instrument_id)
        ).one_or_none()
        return self._records((row,))[0] if row is not None else None

    def get_market_index(self, code: str) -> AnalysisInstrumentRecord | None:
        statement, filters = self._statement(None, None, None)
        row = self._session.execute(
            statement.where(
                *filters,
                Instrument.instrument_type == "market_index",
                canonical_symbol_expression() == code.upper().strip(),
            )
        ).one_or_none()
        return self._records((row,))[0] if row is not None else None

    def get_instruments(
        self, instrument_ids: tuple[int, ...]
    ) -> tuple[AnalysisInstrumentRecord, ...]:
        if not instrument_ids:
            return ()
        statement, filters = self._statement(None, None, None)
        rows = self._session.execute(
            statement.where(*filters, Instrument.id.in_(instrument_ids))
            .order_by(Instrument.id)
        )
        return self._records(tuple(rows))

    def iter_price_bars(
        self, instrument_id: int, price_basis: str
    ) -> tuple[PriceBarRecord, ...]:
        ticker = self._session.scalar(
            select(canonical_symbol_expression()).where(Instrument.id == instrument_id)
        )
        if ticker is None:
            return ()
        rows = self._session.scalars(
            select(PriceBar)
            .where(
                PriceBar.instrument_id == instrument_id,
                PriceBar.price_basis == price_basis,
            )
            .order_by(PriceBar.trading_date)
        )
        return tuple(
            PriceBarRecord(
                ticker=ticker,
                trading_date=row.trading_date,
                open=row.open,
                high=row.high,
                low=row.low,
                close=row.close,
                volume=row.volume,
                currency=row.currency,
                price_scale=row.price_scale,
                price_basis=row.price_basis,
                source=row.source,
                fetched_at=row.fetched_at,
            )
            for row in rows
        )

    def iter_instrument_set_price_bars(
        self, instrument_ids: tuple[int, ...]
    ) -> tuple[AnalysisInstrumentPriceBarRecord, ...]:
        if not instrument_ids:
            return ()
        canonical_basis = self._canonical_basis()
        rows = self._session.execute(
            select(PriceBar, canonical_symbol_expression())
            .join(Instrument, Instrument.id == PriceBar.instrument_id)
            .where(
                Instrument.id.in_(instrument_ids),
                Instrument.is_active.is_(True),
                PriceBar.price_basis == canonical_basis,
            )
            .order_by(Instrument.id, PriceBar.trading_date)
        )
        return tuple(
            AnalysisInstrumentPriceBarRecord(
                instrument_id=bar.instrument_id,
                symbol=symbol,
                trading_date=bar.trading_date,
                open=bar.open,
                high=bar.high,
                low=bar.low,
                close=bar.close,
                volume=bar.volume,
                currency=bar.currency,
                price_scale=bar.price_scale,
                price_basis=bar.price_basis,
                source=bar.source,
                fetched_at=bar.fetched_at,
            )
            for bar, symbol in rows
        )

    @staticmethod
    def _statement(
        scope: str | None,
        search: str | None,
        universe: str | None,
        sector: str | None = None,
        industry: str | None = None,
        venue_code: str | None = None,
    ):
        base_asset = aliased(Asset, name="analysis_base_asset")
        quote_asset = aliased(Asset, name="analysis_quote_asset")
        canonical_basis = SqlAlchemyInstrumentAnalysisRepository._canonical_basis()
        statement = (
            select(
                Instrument.id,
                canonical_symbol_expression(),
                Instrument.instrument_type,
                Company.id.label("company_id"),
                Company.display_name.label("company_name"),
                Company.sector,
                Company.industry,
                Venue.code.label("venue_code"),
                Venue.name.label("venue_name"),
                base_asset.canonical_code.label("base_asset"),
                quote_asset.canonical_code.label("quote_asset"),
                Instrument.currency,
                canonical_basis.label("price_basis"),
                PriceBarCoverage.source.label("price_source"),
                PriceBarCoverage.first_date,
                PriceBarCoverage.last_date,
                PriceBarCoverage.row_count,
            )
            .outerjoin(Company, Company.id == Instrument.company_id)
            .outerjoin(Venue, Venue.id == Instrument.venue_id)
            .outerjoin(base_asset, base_asset.id == Instrument.base_asset_id)
            .outerjoin(quote_asset, quote_asset.id == Instrument.quote_asset_id)
            .outerjoin(
                PriceBarCoverage,
                (PriceBarCoverage.instrument_id == Instrument.id)
                & (PriceBarCoverage.price_basis == canonical_basis),
            )
        )
        filters = [Instrument.is_active.is_(True)]
        if scope == "equity":
            filters.append(Instrument.company_id.is_not(None))
        elif scope == "crypto_spot":
            filters.append(Instrument.instrument_type == "spot")
        elif scope == "reference_rate":
            filters.append(Instrument.instrument_type == "reference_rate")
        elif scope == "market_index":
            filters.append(Instrument.instrument_type == "market_index")
        if search:
            pattern = f"%{search.strip()}%"
            filters.append(or_(
                canonical_symbol_expression().ilike(pattern),
                Company.display_name.ilike(pattern),
                Company.legal_name.ilike(pattern),
                Venue.code.ilike(pattern),
                Venue.name.ilike(pattern),
                base_asset.canonical_code.ilike(pattern),
                quote_asset.canonical_code.ilike(pattern),
            ))
        if universe:
            filters.append(Instrument.memberships.any(
                UniverseMembership.universe.has(Universe.code == universe)
            ))
        if sector:
            filters.append(
                or_(Company.sector.is_(None), Company.sector == "Unknown")
                if sector == "Unknown"
                else Company.sector == sector
            )
        if industry:
            filters.append(Company.industry == industry)
        if venue_code:
            filters.append(Venue.code == venue_code)
        return statement, filters

    @staticmethod
    def _canonical_basis():
        us_venue_ids = select(Venue.id).where(Venue.code.in_((
            "NASDAQ", "NYSE", "NYSE_AMERICAN", "NYSE_ARCA", "CBOE_BZX", "IEX",
        )))
        return case(
            (Instrument.instrument_type == "spot", SPOT_PRICE_BASIS),
            (
                Instrument.instrument_type == "market_index",
                MARKET_INDEX_PRICE_BASIS,
            ),
            (Instrument.venue_id.in_(us_venue_ids), US_EQUITY_PRICE_BASIS),
            else_=DEFAULT_CANONICAL_PRICE_BASIS,
        )

    def _records(self, rows: tuple) -> tuple[AnalysisInstrumentRecord, ...]:
        if not rows:
            return ()
        ids = tuple(row.id for row in rows)
        memberships: dict[int, list[str]] = {instrument_id: [] for instrument_id in ids}
        for instrument_id, universe_code in self._session.execute(
            select(UniverseMembership.instrument_id, Universe.code)
            .join(Universe, Universe.id == UniverseMembership.universe_id)
            .where(UniverseMembership.instrument_id.in_(ids))
            .order_by(UniverseMembership.instrument_id, Universe.code)
        ):
            memberships[instrument_id].append(universe_code)
        return tuple(
            self._record(row, tuple(memberships[row.id])) for row in rows
        )

    @staticmethod
    def _record(row, universes: tuple[str, ...]) -> AnalysisInstrumentRecord:
        return AnalysisInstrumentRecord(
            id=row.id,
            symbol=row.ticker,
            instrument_type=row.instrument_type,
            company_id=row.company_id,
            company_name=row.company_name,
            sector=row.sector,
            industry=row.industry,
            venue_code=row.venue_code,
            venue_name=row.venue_name,
            base_asset=row.base_asset,
            quote_asset=row.quote_asset,
            currency=row.currency,
            price_basis=row.price_basis,
            price_source=row.price_source,
            first_date=row.first_date,
            last_date=row.last_date,
            stored_sessions=int(row.row_count or 0),
            universes=universes,
        )
