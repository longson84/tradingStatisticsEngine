"""SQLAlchemy implementation of the company repository."""
from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from api.db.models import Instrument, Universe, UniverseMembership
from api.repositories.company_repository import (
    CompanyQuery,
    CompanyRecord,
    UniverseRecord,
)


class SqlAlchemyCompanyRepository:
    def __init__(self, session: Session):
        self._session = session

    def list_universes(self) -> tuple[UniverseRecord, ...]:
        rows = self._session.execute(
            select(Universe, func.count(UniverseMembership.id))
            .outerjoin(UniverseMembership)
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

    def list_companies(
        self,
        query: CompanyQuery,
    ) -> tuple[tuple[CompanyRecord, ...], int]:
        filters = [Instrument.market == query.market]
        if query.universe:
            filters.append(
                Instrument.memberships.any(
                    UniverseMembership.universe.has(Universe.code == query.universe)
                )
            )
        if query.search:
            pattern = f"%{query.search.strip()}%"
            filters.append(or_(
                Instrument.ticker.ilike(pattern),
                Instrument.company_name.ilike(pattern),
            ))
        if query.sector:
            filters.append(Instrument.sector == query.sector)
        if query.industry:
            filters.append(Instrument.industry == query.industry)
        if query.exchange:
            filters.append(Instrument.exchange == query.exchange)

        total = int(
            self._session.scalar(
                select(func.count(Instrument.id)).where(*filters)
            )
            or 0
        )
        instruments = self._session.scalars(
            select(Instrument)
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
        return tuple(
            CompanyRecord(
                ticker=instrument.ticker,
                company_name=instrument.company_name,
                market=instrument.market,
                sector=instrument.sector,
                industry=instrument.industry,
                exchange=instrument.exchange,
                lists=tuple(sorted(
                    membership.universe.code
                    for membership in instrument.memberships
                )),
            )
            for instrument in instruments
        ), total
