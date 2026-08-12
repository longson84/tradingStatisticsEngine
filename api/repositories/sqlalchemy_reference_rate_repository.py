"""SQLAlchemy persistence for canonical venue-less reference rates."""
from __future__ import annotations

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from api.db.models import Asset, Instrument, InstrumentSymbol, PriceBarCoverage
from api.repositories.reference_rate_repository import (
    ReferenceRateFacetCount,
    ReferenceRateInstrumentRecord,
    ReferenceRateListFacets,
    ReferenceRateListQuery,
    ReferenceRateListResult,
    ReferenceRateRepository,
    ReferenceRateSummary,
    ReferenceRateWrite,
    REFERENCE_RATE_PRICE_BASIS,
)


class SqlAlchemyReferenceRateRepository(ReferenceRateRepository):
    def __init__(self, session: Session):
        self._session = session

    def upsert_reference_rate(
        self, value: ReferenceRateWrite
    ) -> ReferenceRateInstrumentRecord:
        assets = {
            row.canonical_code: row
            for row in self._session.scalars(
                select(Asset).where(
                    Asset.canonical_code.in_((value.base_asset, value.quote_asset))
                )
            )
        }
        for code, name, asset_type in (
            (value.base_asset, value.base_asset_name, value.base_asset_type),
            (value.quote_asset, value.quote_asset_name, value.quote_asset_type),
        ):
            if code not in assets:
                asset = Asset(
                    canonical_code=code,
                    name=name,
                    asset_type=asset_type,
                    is_active=True,
                    source=value.source,
                )
                self._session.add(asset)
                assets[code] = asset
            elif assets[code].name == code and name != code:
                # Venue catalogs often know only the asset code. Upgrade that
                # placeholder when a descriptive canonical name is available.
                assets[code].name = name
        self._session.flush()

        instrument = self._session.scalar(
            select(Instrument).where(
                Instrument.ticker == value.symbol,
                Instrument.venue_id.is_(None),
                Instrument.instrument_type == "reference_rate",
            )
        )
        if instrument is None:
            instrument = Instrument(
                company_id=None,
                venue_id=None,
                base_asset_id=assets[value.base_asset].id,
                quote_asset_id=assets[value.quote_asset].id,
                settlement_asset_id=assets[value.quote_asset].id,
                ticker=value.symbol,
                instrument_type="reference_rate",
                currency=value.quote_asset,
                is_active=True,
                source=value.source,
            )
            self._session.add(instrument)
            self._session.flush()
        else:
            if instrument.instrument_type != "reference_rate":
                raise ValueError(
                    f"Venue-less CRYPTO instrument {value.symbol} is not a reference rate"
                )
            instrument.company_id = None
            instrument.venue_id = None
            instrument.base_asset_id = assets[value.base_asset].id
            instrument.quote_asset_id = assets[value.quote_asset].id
            instrument.settlement_asset_id = assets[value.quote_asset].id
            instrument.currency = value.quote_asset
            instrument.is_active = True
            instrument.source = value.source

        symbol = self._session.scalar(
            select(InstrumentSymbol).where(
                InstrumentSymbol.namespace == value.source,
                InstrumentSymbol.symbol == value.symbol,
                InstrumentSymbol.valid_to.is_(None),
            )
        )
        if symbol is None:
            self._session.add(InstrumentSymbol(
                instrument_id=instrument.id,
                namespace=value.source,
                symbol=value.symbol,
                is_primary=True,
                source=value.source,
            ))
        elif symbol.instrument_id != instrument.id:
            raise ValueError(
                f"Symbol {value.source}:{value.symbol} belongs to another instrument"
            )
        self._session.flush()
        result = self.get_reference_rate(value.symbol)
        if result is None:  # pragma: no cover - defensive transaction invariant
            raise RuntimeError(f"Failed to persist reference rate {value.symbol}")
        return result

    def get_reference_rate(
        self, symbol: str
    ) -> ReferenceRateInstrumentRecord | None:
        statement = self._row_statement().where(
            Instrument.ticker == symbol.upper().strip()
        )
        row = self._session.execute(statement).one_or_none()
        return self._record(row) if row is not None else None

    def list_reference_rates(
        self, query: ReferenceRateListQuery
    ) -> ReferenceRateListResult:
        base = Asset.__table__.alias("reference_base_asset")
        quote = Asset.__table__.alias("reference_quote_asset")
        common = [Instrument.instrument_type == "reference_rate"]
        if query.search:
            pattern = f"%{query.search.strip()}%"
            common.append(or_(
                Instrument.ticker.ilike(pattern),
                base.c.canonical_code.ilike(pattern),
                base.c.name.ilike(pattern),
                quote.c.canonical_code.ilike(pattern),
                quote.c.name.ilike(pattern),
            ))
        row_filters = list(common)
        if query.base_asset:
            row_filters.append(base.c.canonical_code == query.base_asset.upper())
        if query.quote_asset:
            row_filters.append(quote.c.canonical_code == query.quote_asset.upper())
        if query.is_active is not None:
            row_filters.append(Instrument.is_active.is_(query.is_active))

        joined = (
            select(Instrument.id)
            .join(base, base.c.id == Instrument.base_asset_id)
            .join(quote, quote.c.id == Instrument.quote_asset_id)
        )
        total = int(self._session.scalar(
            joined.with_only_columns(func.count(Instrument.id)).where(*row_filters)
        ) or 0)
        rows = tuple(
            self._record(row)
            for row in self._session.execute(
                self._row_statement(base, quote)
                .where(*row_filters)
                .order_by(Instrument.ticker, Instrument.id)
                .offset(query.offset)
                .limit(query.limit)
            )
        )

        facet_filters = list(common)
        if query.is_active is not None:
            facet_filters.append(Instrument.is_active.is_(query.is_active))
        base_rows = self._session.execute(
            select(base.c.canonical_code, func.count(Instrument.id))
            .join(base, base.c.id == Instrument.base_asset_id)
            .join(quote, quote.c.id == Instrument.quote_asset_id)
            .where(*facet_filters)
            .group_by(base.c.canonical_code)
            .order_by(base.c.canonical_code)
        )
        quote_rows = self._session.execute(
            select(quote.c.canonical_code, func.count(Instrument.id))
            .join(base, base.c.id == Instrument.base_asset_id)
            .join(quote, quote.c.id == Instrument.quote_asset_id)
            .where(*facet_filters)
            .group_by(quote.c.canonical_code)
            .order_by(quote.c.canonical_code)
        )

        status_filters = list(common)
        if query.base_asset:
            status_filters.append(base.c.canonical_code == query.base_asset.upper())
        if query.quote_asset:
            status_filters.append(quote.c.canonical_code == query.quote_asset.upper())
        active_count, inactive_count = self._session.execute(
            select(
                func.sum(case((Instrument.is_active.is_(True), 1), else_=0)),
                func.sum(case((Instrument.is_active.is_(False), 1), else_=0)),
            )
            .join(base, base.c.id == Instrument.base_asset_id)
            .join(quote, quote.c.id == Instrument.quote_asset_id)
            .where(*status_filters)
        ).one()

        summary = self._session.execute(
            select(
                func.count(Instrument.id),
                func.sum(case((Instrument.is_active.is_(True), 1), else_=0)),
                func.sum(case((Instrument.is_active.is_(False), 1), else_=0)),
                func.count(PriceBarCoverage.instrument_id),
                func.min(PriceBarCoverage.first_date),
                func.max(PriceBarCoverage.last_date),
            )
            .outerjoin(
                PriceBarCoverage,
                (PriceBarCoverage.instrument_id == Instrument.id)
                & (PriceBarCoverage.price_basis == REFERENCE_RATE_PRICE_BASIS),
            )
            .where(Instrument.instrument_type == "reference_rate")
        ).one()
        return ReferenceRateListResult(
            total=total,
            rows=rows,
            facets=ReferenceRateListFacets(
                base_assets=tuple(
                    ReferenceRateFacetCount(value=value, count=int(count))
                    for value, count in base_rows
                ),
                quote_assets=tuple(
                    ReferenceRateFacetCount(value=value, count=int(count))
                    for value, count in quote_rows
                ),
                active_count=int(active_count or 0),
                inactive_count=int(inactive_count or 0),
            ),
            summary=ReferenceRateSummary(
                instrument_count=int(summary[0] or 0),
                active_count=int(summary[1] or 0),
                inactive_count=int(summary[2] or 0),
                with_history_count=int(summary[3] or 0),
                earliest_session=summary[4],
                latest_session=summary[5],
            ),
        )

    def _row_statement(self, base=None, quote=None):
        if base is None:
            base = Asset.__table__.alias("reference_base_asset")
        if quote is None:
            quote = Asset.__table__.alias("reference_quote_asset")
        return (
            select(
                Instrument.id,
                Instrument.ticker,
                base.c.canonical_code,
                base.c.name,
                quote.c.canonical_code,
                quote.c.name,
                Instrument.is_active,
                Instrument.source,
                PriceBarCoverage.first_date,
                PriceBarCoverage.last_date,
                PriceBarCoverage.row_count,
                PriceBarCoverage.source,
                PriceBarCoverage.fetched_at,
            )
            .join(base, base.c.id == Instrument.base_asset_id)
            .join(quote, quote.c.id == Instrument.quote_asset_id)
            .outerjoin(
                PriceBarCoverage,
                (PriceBarCoverage.instrument_id == Instrument.id)
                & (PriceBarCoverage.price_basis == REFERENCE_RATE_PRICE_BASIS),
            )
            .where(Instrument.instrument_type == "reference_rate")
        )

    @staticmethod
    def _record(row) -> ReferenceRateInstrumentRecord:
        return ReferenceRateInstrumentRecord(
            id=row[0],
            symbol=row[1],
            base_asset=row[2],
            base_asset_name=row[3],
            quote_asset=row[4],
            quote_asset_name=row[5],
            is_active=row[6],
            catalog_source=row[7],
            first_date=row[8],
            last_date=row[9],
            stored_sessions=int(row[10] or 0),
            price_source=row[11],
            price_fetched_at=row[12],
        )
