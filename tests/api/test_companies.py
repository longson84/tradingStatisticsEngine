from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import create_engine, select

from api.db.company_import import import_company_universes
from api.db.models import Base, Instrument, PriceBarCoverage
from api.main import app
from api.repositories.sqlalchemy_company_repository import SqlAlchemyCompanyRepository
from api.routes.companies import list_companies, list_company_universes
from api.services.company_service import CompanyService
from sqlalchemy.orm import Session


def _service() -> tuple[CompanyService, Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    import_company_universes(engine)
    session = Session(engine)
    return CompanyService(SqlAlchemyCompanyRepository(session)), session


def test_company_service_returns_one_company_with_all_memberships():
    service, session = _service()
    try:
        result = service.list_companies("US_ALL", search="AAPL")
    finally:
        session.close()

    assert result.total == 1
    assert result.companies[0].ticker == "AAPL"
    assert result.companies[0].lists == ("US100", "US30", "US500")


def test_company_route_contract_has_only_canonical_company_fields():
    service, session = _service()
    try:
        instrument = session.scalar(select(Instrument).where(
            Instrument.market == "VN",
            Instrument.ticker == "FPT",
        ))
        assert instrument is not None
        session.add(PriceBarCoverage(
            instrument_id=instrument.id,
            price_basis="provider_unspecified",
            first_date=date(2006, 12, 13),
            last_date=date(2026, 8, 7),
            row_count=4_897,
            source="vnstock-data-3.2.7-vci",
            fetched_at=datetime(2026, 8, 8, tzinfo=UTC),
        ))
        session.flush()
        response = list_companies(
            service,
            universe="VN100",
            search="FPT",
            sector=None,
            industry=None,
            exchange=None,
            offset=0,
            limit=5000,
        )
    finally:
        session.close()

    company = next(row for row in response.companies if row.ticker == "FPT")
    assert company.model_dump() == {
        "ticker": "FPT",
        "company_name": "FPT Corporation",
        "market": "VN",
        "sector": "Information Technology",
        "industry": "Công nghệ và thông tin",
        "exchange": "HOSE",
        "lists": ["VN100", "VN30", "VNALL"],
        "first_session": date(2006, 12, 13),
        "last_session": date(2026, 8, 7),
        "stored_sessions": 4_897,
    }


def test_company_universe_route_includes_database_and_combined_views():
    service, session = _service()
    try:
        response = list_company_universes(service)
    finally:
        session.close()

    assert [row.id for row in response.universes] == [
        "US_ALL", "US100", "US2000", "US500", "US30",
        "VN_ALL", "VNALL", "VN100", "VN30", "VNMID", "VNSML",
    ]
    assert response.universes[0].company_count == 2472
    assert response.universes[5].company_count == 315


def test_openapi_company_contract_is_generated_from_canonical_schema():
    schema = app.openapi()

    assert schema["paths"]["/companies"]["get"]["operationId"] == "listCompanies"
    assert not any(path.startswith("/symbol-lists") for path in schema["paths"])
    properties = schema["components"]["schemas"]["CompanyResponse"]["properties"]
    assert set(properties) == {
        "ticker", "company_name", "market", "sector", "industry", "exchange",
        "lists", "first_session", "last_session", "stored_sessions",
    }
