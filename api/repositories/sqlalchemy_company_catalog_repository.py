"""SQLAlchemy company catalog projection."""
from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from api.db.models import (
    Company,
    Instrument,
    InstrumentSymbol,
    UniverseMembership,
    Venue,
)
from api.instrument_symbols import canonical_symbol
from api.repositories.company_catalog_repository import (
    CompanyCatalogQuery,
    CompanyCatalogRecord,
    CompanyCatalogFacetCount,
    CompanyCatalogFacets,
    CompanyIdentifierRecord,
    CompanyInstrumentRecord,
)


class SqlAlchemyCompanyCatalogRepository:
    def __init__(self, session: Session):
        self._session = session

    def list_companies(
        self,
        query: CompanyCatalogQuery,
    ) -> tuple[tuple[CompanyCatalogRecord, ...], int, CompanyCatalogFacets]:
        base_filters = [Company.instruments.any()]
        search_filter = None
        if query.search:
            pattern = f"%{query.search.strip()}%"
            search_filter = or_(
                Company.display_name.ilike(pattern),
                Company.legal_name.ilike(pattern),
                Company.instruments.any(
                    Instrument.symbols.any(
                        (InstrumentSymbol.namespace == "canonical")
                        & InstrumentSymbol.valid_to.is_(None)
                        & InstrumentSymbol.is_primary.is_(True)
                        & InstrumentSymbol.symbol.ilike(pattern)
                    )
                ),
            )
            base_filters.append(search_filter)
        filters = list(base_filters)
        if query.listing_country:
            filters.append(
                Company.instruments.any(
                    Instrument.venue.has(
                        Venue.country_code == query.listing_country
                    )
                )
            )
        if query.sector:
            filters.append(
                or_(Company.sector.is_(None), Company.sector == "Unknown")
                if query.sector == "Unknown"
                else Company.sector == query.sector
            )

        total = int(
            self._session.scalar(select(func.count(Company.id)).where(*filters)) or 0
        )
        companies = self._session.scalars(
            select(Company)
            .where(*filters)
            .options(
                selectinload(Company.identifiers),
                selectinload(Company.instruments)
                .selectinload(Instrument.venue),
                selectinload(Company.instruments)
                .selectinload(Instrument.symbols),
                selectinload(Company.instruments)
                .selectinload(Instrument.memberships)
                .selectinload(UniverseMembership.universe),
            )
            .order_by(Company.display_name, Company.id)
            .offset(query.offset)
            .limit(query.limit)
        ).all()
        listing_country_rows = self._session.execute(
            select(Venue.country_code, func.count(func.distinct(Company.id)))
            .join(Instrument, Instrument.venue_id == Venue.id)
            .join(Company, Company.id == Instrument.company_id)
            .where(*base_filters, Venue.country_code.is_not(None))
            .group_by(Venue.country_code)
            .order_by(Venue.country_code)
        )
        sector_filters = list(base_filters)
        if query.listing_country:
            sector_filters.append(
                Company.instruments.any(
                    Instrument.venue.has(
                        Venue.country_code == query.listing_country
                    )
                )
            )
        sector_value = func.coalesce(Company.sector, "Unknown")
        sector_rows = self._session.execute(
            select(sector_value, func.count(Company.id))
            .where(*sector_filters)
            .group_by(sector_value)
            .order_by(sector_value)
        )
        facets = CompanyCatalogFacets(
            listing_countries=tuple(
                CompanyCatalogFacetCount(value=value, count=int(count))
                for value, count in listing_country_rows
            ),
            sectors=tuple(
                CompanyCatalogFacetCount(value=value, count=int(count))
                for value, count in sector_rows
            ),
        )
        return tuple(self._record(company) for company in companies), total, facets

    @staticmethod
    def _record(company: Company) -> CompanyCatalogRecord:
        return CompanyCatalogRecord(
            id=company.id,
            display_name=company.display_name,
            legal_name=company.legal_name,
            domicile_country_code=company.domicile_country_code,
            listing_country_codes=tuple(
                sorted({
                    instrument.venue.country_code
                    for instrument in company.instruments
                    if instrument.venue is not None
                    and instrument.venue.country_code is not None
                })
            ),
            sector=company.sector,
            industry=company.industry,
            is_active=company.is_active,
            identifiers=tuple(
                CompanyIdentifierRecord(
                    namespace=identifier.namespace,
                    value=identifier.value,
                )
                for identifier in sorted(
                    company.identifiers,
                    key=lambda row: (row.namespace, row.value),
                )
            ),
            instruments=tuple(
                CompanyInstrumentRecord(
                    id=instrument.id,
                    symbol=canonical_symbol(instrument),
                    instrument_type=instrument.instrument_type,
                    share_class=instrument.share_class,
                    venue_code=(instrument.venue.code if instrument.venue else None),
                    venue_country_code=(
                        instrument.venue.country_code
                        if instrument.venue
                        else None
                    ),
                    currency=instrument.currency,
                    is_active=instrument.is_active,
                    universes=tuple(sorted(
                        membership.universe.code
                        for membership in instrument.memberships
                    )),
                )
                for instrument in sorted(
                    company.instruments,
                    key=lambda row: (
                        row.venue.code if row.venue else "",
                        canonical_symbol(row),
                    ),
                )
            ),
        )
