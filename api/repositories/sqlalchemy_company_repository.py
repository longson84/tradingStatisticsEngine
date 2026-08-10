"""SQLAlchemy implementation of the company repository."""
from __future__ import annotations

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from api.db.models import (
    Company,
    Instrument,
    PriceBarCoverage,
    Universe,
    UniverseMembership,
)
from api.repositories.company_repository import (
    CompanyQuery,
    CompanyRecord,
    CompanyListFacets,
    FacetCount,
    UniverseRecord,
)


class SqlAlchemyCompanyRepository:
    def __init__(self, session: Session):
        self._session = session

    def list_universes(self) -> tuple[UniverseRecord, ...]:
        rows = self._session.execute(
            select(Universe, func.count(UniverseMembership.id))
            .outerjoin(UniverseMembership)
            .where(Universe.market.in_(("US", "VN")))
            .group_by(Universe.id)
            .order_by(Universe.code)
        )
        return tuple(
            UniverseRecord(
                code=universe.code,
                name=universe.name,
                market=universe.market,
                description=universe.description,
                as_of=universe.as_of,
                fetched_at=universe.fetched_at,
                company_count=int(company_count),
            )
            for universe, company_count in rows
        )

    def count_companies(self, query: CompanyQuery) -> int:
        filters = [Instrument.market == query.market]
        if query.universe:
            filters.append(
                Instrument.memberships.any(
                    UniverseMembership.universe.has(Universe.code == query.universe)
                )
            )
        return int(
            self._session.scalar(
                select(func.count(Instrument.id)).where(*filters)
            )
            or 0
        )
    def list_companies(
        self,
        query: CompanyQuery,
    ) -> tuple[tuple[CompanyRecord, ...], int, CompanyListFacets]:
        base_filters = [Instrument.market == query.market]
        if query.search:
            pattern = f"%{query.search.strip()}%"
            base_filters.append(or_(
                Instrument.ticker.ilike(pattern),
                Company.display_name.ilike(pattern),
            ))
        if query.exchange:
            base_filters.append(Instrument.exchange == query.exchange)

        filters = list(base_filters)
        if query.universe:
            filters.append(
                Instrument.memberships.any(
                    UniverseMembership.universe.has(Universe.code == query.universe)
                )
            )
        if query.sector:
            filters.append(
                or_(Company.sector.is_(None), Company.sector == "Unknown")
                if query.sector == "Unknown"
                else Company.sector == query.sector
            )
        if query.industry:
            filters.append(Company.industry == query.industry)

        total = int(
            self._session.scalar(
                select(func.count(Instrument.id)).join(Instrument.company).where(*filters)
            )
            or 0
        )
        rows = self._session.execute(
            select(Instrument, Company, PriceBarCoverage)
            .join(Instrument.company)
            .outerjoin(
                PriceBarCoverage,
                and_(
                    PriceBarCoverage.instrument_id == Instrument.id,
                    PriceBarCoverage.price_basis == query.price_basis,
                ),
            )
            .where(*filters)
            .options(
                selectinload(Instrument.memberships).selectinload(
                    UniverseMembership.universe
                )
            )
            .order_by(Instrument.ticker)
            .offset(query.offset)
            .limit(query.limit)
        ).all()
        records = tuple(
            CompanyRecord(
                ticker=instrument.ticker,
                company_name=company.display_name,
                market=instrument.market,
                sector=company.sector,
                industry=company.industry,
                exchange=instrument.exchange,
                lists=tuple(sorted(
                    membership.universe.code
                    for membership in instrument.memberships
                )),
                first_session=(coverage.first_date if coverage else None),
                last_session=(coverage.last_date if coverage else None),
                stored_sessions=(int(coverage.row_count) if coverage else 0),
            )
            for instrument, company, coverage in rows
        )

        all_count = int(
            self._session.scalar(
                select(func.count(Instrument.id))
                .join(Instrument.company)
                .where(*base_filters)
            )
            or 0
        )
        sector_filters = list(base_filters)
        if query.universe:
            sector_filters.append(
                Instrument.memberships.any(
                    UniverseMembership.universe.has(Universe.code == query.universe)
                )
            )
        sector_value = func.coalesce(Company.sector, "Unknown")
        sector_rows = self._session.execute(
            select(sector_value, func.count(Instrument.id))
            .join(Instrument.company)
            .where(*sector_filters)
            .group_by(sector_value)
            .order_by(sector_value)
        )
        universe_rows = self._session.execute(
            select(Universe.code, func.count(UniverseMembership.id))
            .join(UniverseMembership)
            .join(Instrument)
            .join(Instrument.company)
            .where(*base_filters)
            .group_by(Universe.code)
            .order_by(Universe.code)
        )
        facets = CompanyListFacets(
            all_count=all_count,
            sectors=tuple(
                FacetCount(value=value, count=int(count))
                for value, count in sector_rows
            ),
            universes=tuple(
                FacetCount(value=value, count=int(count))
                for value, count in universe_rows
            ),
        )
        return records, total, facets
