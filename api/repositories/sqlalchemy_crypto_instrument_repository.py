"""SQLAlchemy persistence for canonical crypto assets and spot instruments."""
from __future__ import annotations

from sqlalchemy import case, delete, func, or_, select
from sqlalchemy.orm import Session, selectinload

from api.db.models import (
    Asset,
    Instrument,
    InstrumentSymbol,
    PriceBarCoverage,
    Universe,
    UniverseMembership,
    Venue,
)
from api.repositories.crypto_instrument_repository import (
    CryptoInstrumentRepository,
    SpotCatalogSyncResult,
    SpotCatalogWrite,
    SpotInstrumentRecord,
    SpotInstrumentFacetCount,
    SpotInstrumentListFacets,
    SpotInstrumentListQuery,
    SpotInstrumentListRecord,
    SpotInstrumentListResult,
    SpotInstrumentSummary,
    SpotInstrumentVenueFacet,
)
from api.venue_calendars import venue_calendar
from api.instrument_symbols import (
    canonical_symbol,
    canonical_symbol_expression,
    new_instrument,
)


SPOT_PRICE_BASIS = "venue_unadjusted"


class SqlAlchemyCryptoInstrumentRepository(CryptoInstrumentRepository):
    def __init__(self, session: Session):
        self._session = session

    def sync_spot_catalog(self, catalog: SpotCatalogWrite) -> SpotCatalogSyncResult:
        schedule = venue_calendar(catalog.venue_code)
        venue = self._session.scalar(select(Venue).where(Venue.code == catalog.venue_code))
        if venue is None:
            venue = Venue(
                code=catalog.venue_code,
                name=catalog.venue_name,
                venue_type="exchange",
                timezone_name=schedule.timezone_name,
                trading_calendar_code=schedule.trading_calendar_code,
                session_cutoff_time=schedule.session_cutoff_time,
                is_active=True,
                source=catalog.source,
            )
            self._session.add(venue)
            self._session.flush()
        else:
            venue.name = catalog.venue_name
            venue.timezone_name = schedule.timezone_name
            venue.trading_calendar_code = schedule.trading_calendar_code
            venue.session_cutoff_time = schedule.session_cutoff_time
            venue.is_active = True
            venue.source = catalog.source

        asset_codes = {row.code for row in catalog.assets}
        assets = {
            row.canonical_code: row
            for row in self._session.scalars(
                select(Asset).where(Asset.canonical_code.in_(asset_codes))
            )
        }
        added_assets = 0
        for value in catalog.assets:
            asset = assets.get(value.code)
            if asset is None:
                asset = Asset(
                    canonical_code=value.code,
                    name=value.name,
                    asset_type=value.asset_type,
                    is_active=True,
                    source=catalog.source,
                )
                self._session.add(asset)
                assets[value.code] = asset
                added_assets += 1
            else:
                asset.is_active = True
                # exchangeInfo supplies codes, not authoritative asset names or
                # classifications. Preserve richer canonical metadata already
                # reconciled from another source.
        self._session.flush()

        existing = {
            canonical_symbol(row): row
            for row in self._session.scalars(
                select(Instrument).where(
                    Instrument.venue_id == venue.id,
                    Instrument.instrument_type == "spot",
                ).options(selectinload(Instrument.symbols))
            )
        }
        added = 0
        updated = 0
        active_ids: set[int] = set()
        seen_symbols: set[str] = set()
        for value in catalog.instruments:
            seen_symbols.add(value.symbol)
            instrument = existing.get(value.symbol)
            base_asset = assets[value.base_asset]
            quote_asset = assets[value.quote_asset]
            desired = (
                base_asset.id,
                quote_asset.id,
                value.is_active,
                value.base_precision,
                value.quote_precision,
                value.price_tick_size,
                value.quantity_step_size,
                value.minimum_quantity,
                value.minimum_notional,
            )
            if instrument is None:
                instrument = new_instrument(
                    value.symbol,
                    source=catalog.source,
                    company_id=None,
                    venue_id=venue.id,
                    base_asset_id=base_asset.id,
                    quote_asset_id=quote_asset.id,
                    settlement_asset_id=quote_asset.id,
                    instrument_type="spot",
                    currency=value.quote_asset,
                    base_precision=value.base_precision,
                    quote_precision=value.quote_precision,
                    price_tick_size=value.price_tick_size,
                    quantity_step_size=value.quantity_step_size,
                    minimum_quantity=value.minimum_quantity,
                    minimum_notional=value.minimum_notional,
                    is_active=value.is_active,
                )
                self._session.add(instrument)
                self._session.flush()
                self._session.add(InstrumentSymbol(
                    instrument_id=instrument.id,
                    namespace="binance_spot",
                    symbol=value.symbol,
                    is_primary=True,
                    source=catalog.source,
                ))
                existing[value.symbol] = instrument
                added += 1
            else:
                current = (
                    instrument.base_asset_id,
                    instrument.quote_asset_id,
                    instrument.is_active,
                    instrument.base_precision,
                    instrument.quote_precision,
                    instrument.price_tick_size,
                    instrument.quantity_step_size,
                    instrument.minimum_quantity,
                    instrument.minimum_notional,
                )
                if current != desired:
                    updated += 1
                instrument.company_id = None
                instrument.base_asset_id = base_asset.id
                instrument.quote_asset_id = quote_asset.id
                instrument.settlement_asset_id = quote_asset.id
                instrument.instrument_type = "spot"
                instrument.currency = value.quote_asset
                instrument.base_precision = value.base_precision
                instrument.quote_precision = value.quote_precision
                instrument.price_tick_size = value.price_tick_size
                instrument.quantity_step_size = value.quantity_step_size
                instrument.minimum_quantity = value.minimum_quantity
                instrument.minimum_notional = value.minimum_notional
                instrument.is_active = value.is_active
                instrument.source = catalog.source
            if value.is_active:
                active_ids.add(instrument.id)

        deactivated = 0
        for symbol, instrument in existing.items():
            if symbol not in seen_symbols and instrument.is_active:
                instrument.is_active = False
                deactivated += 1

        universe = self._session.scalar(
            select(Universe).where(Universe.code == catalog.universe_code)
        )
        if universe is None:
            universe = Universe(
                code=catalog.universe_code,
                name=catalog.universe_name,
                description="Currently active Binance Spot instruments.",
                as_of=catalog.fetched_at.date().isoformat(),
                fetched_at=catalog.fetched_at,
                source=catalog.source,
            )
            self._session.add(universe)
            self._session.flush()
        else:
            universe.name = catalog.universe_name
            universe.description = "Currently active Binance Spot instruments."
            universe.as_of = catalog.fetched_at.date().isoformat()
            universe.fetched_at = catalog.fetched_at
            universe.source = catalog.source
        self._session.execute(
            delete(UniverseMembership).where(
                UniverseMembership.universe_id == universe.id
            )
        )
        self._session.add_all(
            UniverseMembership(
                universe_id=universe.id,
                instrument_id=instrument_id,
                source=catalog.source,
                fetched_at=catalog.fetched_at,
            )
            for instrument_id in sorted(active_ids)
        )
        return SpotCatalogSyncResult(
            received_instruments=len(catalog.instruments),
            active_instruments=len(active_ids),
            added_instruments=added,
            updated_instruments=updated,
            deactivated_instruments=deactivated,
            added_assets=added_assets,
        )

    def list_spot_instruments(
        self,
        venue_code: str,
        *,
        symbols: tuple[str, ...] = (),
        quote_assets: tuple[str, ...] = (),
    ) -> tuple[SpotInstrumentRecord, ...]:
        base = Asset.__table__.alias("base_asset")
        quote = Asset.__table__.alias("quote_asset")
        statement = (
            select(
                Instrument.id,
                canonical_symbol_expression(),
                base.c.canonical_code,
                quote.c.canonical_code,
                PriceBarCoverage.first_date,
                PriceBarCoverage.last_date,
            )
            .join(Venue, Venue.id == Instrument.venue_id)
            .join(base, base.c.id == Instrument.base_asset_id)
            .join(quote, quote.c.id == Instrument.quote_asset_id)
            .outerjoin(
                PriceBarCoverage,
                (PriceBarCoverage.instrument_id == Instrument.id)
                & (PriceBarCoverage.price_basis == SPOT_PRICE_BASIS),
            )
            .where(
                Venue.code == venue_code,
                Instrument.instrument_type == "spot",
                Instrument.is_active.is_(True),
            )
            .order_by(canonical_symbol_expression())
        )
        if symbols:
            statement = statement.where(canonical_symbol_expression().in_(symbols))
        if quote_assets:
            statement = statement.where(quote.c.canonical_code.in_(quote_assets))
        return tuple(
            SpotInstrumentRecord(
                id=instrument_id,
                symbol=symbol,
                base_asset=base_asset,
                quote_asset=quote_asset,
                first_date=first_date,
                last_date=last_date,
            )
            for (
                instrument_id,
                symbol,
                base_asset,
                quote_asset,
                first_date,
                last_date,
            ) in self._session.execute(statement)
        )

    def list_spot_catalog(
        self,
        query: SpotInstrumentListQuery,
    ) -> SpotInstrumentListResult:
        base = Asset.__table__.alias("market_base_asset")
        quote = Asset.__table__.alias("market_quote_asset")
        base_filters = [Instrument.instrument_type == "spot"]
        if query.search:
            pattern = f"%{query.search.strip()}%"
            base_filters.append(or_(
                canonical_symbol_expression().ilike(pattern),
                base.c.canonical_code.ilike(pattern),
                quote.c.canonical_code.ilike(pattern),
            ))

        row_filters = list(base_filters)
        if query.venue_code:
            row_filters.append(Venue.code == query.venue_code.upper().strip())
        if query.quote_asset:
            row_filters.append(
                quote.c.canonical_code == query.quote_asset.upper().strip()
            )
        if query.is_active is not None:
            row_filters.append(Instrument.is_active.is_(query.is_active))

        joined = (
            select(Instrument.id)
            .join(Venue, Venue.id == Instrument.venue_id)
            .join(base, base.c.id == Instrument.base_asset_id)
            .join(quote, quote.c.id == Instrument.quote_asset_id)
        )
        total = int(self._session.scalar(
            joined.with_only_columns(func.count(Instrument.id)).where(*row_filters)
        ) or 0)

        statement = (
            select(
                Instrument.id,
                Venue.code,
                Venue.name,
                canonical_symbol_expression(),
                base.c.canonical_code,
                quote.c.canonical_code,
                Instrument.is_active,
                Instrument.price_tick_size,
                Instrument.quantity_step_size,
                Instrument.minimum_quantity,
                Instrument.minimum_notional,
                PriceBarCoverage.first_date,
                PriceBarCoverage.last_date,
                PriceBarCoverage.row_count,
                PriceBarCoverage.source,
            )
            .join(Venue, Venue.id == Instrument.venue_id)
            .join(base, base.c.id == Instrument.base_asset_id)
            .join(quote, quote.c.id == Instrument.quote_asset_id)
            .outerjoin(
                PriceBarCoverage,
                (PriceBarCoverage.instrument_id == Instrument.id)
                & (PriceBarCoverage.price_basis == SPOT_PRICE_BASIS),
            )
            .where(*row_filters)
            .order_by(
                Instrument.is_active.desc(),
                canonical_symbol_expression(),
                Venue.code,
                Instrument.id,
            )
            .offset(query.offset)
            .limit(query.limit)
        )
        rows = tuple(
            SpotInstrumentListRecord(
                id=instrument_id,
                venue_code=venue_code,
                venue_name=venue_name,
                symbol=symbol,
                base_asset=base_asset,
                quote_asset=quote_asset,
                is_active=is_active,
                price_tick_size=price_tick_size,
                quantity_step_size=quantity_step_size,
                minimum_quantity=minimum_quantity,
                minimum_notional=minimum_notional,
                first_date=first_date,
                last_date=last_date,
                stored_sessions=int(stored_sessions or 0),
                price_source=price_source,
            )
            for (
                instrument_id,
                venue_code,
                venue_name,
                symbol,
                base_asset,
                quote_asset,
                is_active,
                price_tick_size,
                quantity_step_size,
                minimum_quantity,
                minimum_notional,
                first_date,
                last_date,
                stored_sessions,
                price_source,
            ) in self._session.execute(statement)
        )

        quote_filters = list(base_filters)
        if query.venue_code:
            quote_filters.append(Venue.code == query.venue_code.upper().strip())
        if query.is_active is not None:
            quote_filters.append(Instrument.is_active.is_(query.is_active))
        quote_rows = self._session.execute(
            select(quote.c.canonical_code, func.count(Instrument.id))
            .join(Venue, Venue.id == Instrument.venue_id)
            .join(base, base.c.id == Instrument.base_asset_id)
            .join(quote, quote.c.id == Instrument.quote_asset_id)
            .where(*quote_filters)
            .group_by(quote.c.canonical_code)
            .order_by(func.count(Instrument.id).desc(), quote.c.canonical_code)
        )

        status_filters = list(base_filters)
        if query.venue_code:
            status_filters.append(Venue.code == query.venue_code.upper().strip())
        if query.quote_asset:
            status_filters.append(
                quote.c.canonical_code == query.quote_asset.upper().strip()
            )
        active_count, inactive_count = self._session.execute(
            select(
                func.sum(case((Instrument.is_active.is_(True), 1), else_=0)),
                func.sum(case((Instrument.is_active.is_(False), 1), else_=0)),
            )
            .join(Venue, Venue.id == Instrument.venue_id)
            .join(base, base.c.id == Instrument.base_asset_id)
            .join(quote, quote.c.id == Instrument.quote_asset_id)
            .where(*status_filters)
        ).one()

        venue_filters = list(base_filters)
        if query.quote_asset:
            venue_filters.append(
                quote.c.canonical_code == query.quote_asset.upper().strip()
            )
        if query.is_active is not None:
            venue_filters.append(Instrument.is_active.is_(query.is_active))
        venue_rows = self._session.execute(
            select(Venue.code, Venue.name, func.count(Instrument.id))
            .join(Instrument, Instrument.venue_id == Venue.id)
            .join(base, base.c.id == Instrument.base_asset_id)
            .join(quote, quote.c.id == Instrument.quote_asset_id)
            .where(*venue_filters)
            .group_by(Venue.code, Venue.name)
            .order_by(Venue.name)
        )

        summary_filters = [Instrument.instrument_type == "spot"]
        if query.venue_code:
            summary_filters.append(Venue.code == query.venue_code.upper().strip())
        summary_counts = self._session.execute(
            select(
                func.count(Instrument.id),
                func.sum(case((Instrument.is_active.is_(True), 1), else_=0)),
                func.sum(case((Instrument.is_active.is_(False), 1), else_=0)),
                func.count(PriceBarCoverage.instrument_id),
            )
            .join(Venue, Venue.id == Instrument.venue_id)
            .outerjoin(
                PriceBarCoverage,
                (PriceBarCoverage.instrument_id == Instrument.id)
                & (PriceBarCoverage.price_basis == SPOT_PRICE_BASIS),
            )
            .where(*summary_filters)
        ).one()
        catalog_query = select(func.max(Universe.fetched_at))
        if query.venue_code:
            catalog_query = catalog_query.where(
                Universe.code == query.venue_code.upper().strip()
            )
        else:
            catalog_query = catalog_query.where(
                Universe.code.in_(select(Venue.code))
            )
        catalog_fetched_at = self._session.scalar(catalog_query)
        instrument_count, summary_active, summary_inactive, with_history = summary_counts
        return SpotInstrumentListResult(
            total=total,
            rows=rows,
            facets=SpotInstrumentListFacets(
                venues=tuple(
                    SpotInstrumentVenueFacet(code=code, name=name, count=int(count))
                    for code, name, count in venue_rows
                ),
                quote_assets=tuple(
                    SpotInstrumentFacetCount(value=value, count=int(count))
                    for value, count in quote_rows
                ),
                active_count=int(active_count or 0),
                inactive_count=int(inactive_count or 0),
            ),
            summary=SpotInstrumentSummary(
                instrument_count=int(instrument_count or 0),
                active_count=int(summary_active or 0),
                inactive_count=int(summary_inactive or 0),
                with_history_count=int(with_history or 0),
                catalog_fetched_at=catalog_fetched_at,
            ),
        )
