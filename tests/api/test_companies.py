from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import create_engine, select

from api.db.company_import import import_company_universes
from api.db.models import Base, Instrument, PriceBarCoverage
from api.main import app
from api.repositories.sqlalchemy_company_repository import SqlAlchemyCompanyRepository
from api.repositories.sqlalchemy_company_catalog_repository import (
    SqlAlchemyCompanyCatalogRepository,
)
from api.routes.companies import (
    list_companies,
    list_company_catalog,
    list_company_universes,
)
from api.services.company_service import CompanyService
from api.services.company_catalog_service import CompanyCatalogService
from sqlalchemy.orm import Session


def _service() -> tuple[CompanyService, Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    import_company_universes(engine)
    session = Session(engine)
    return CompanyService(SqlAlchemyCompanyRepository(session)), session


def _catalog_service() -> tuple[CompanyCatalogService, Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    import_company_universes(engine)
    session = Session(engine)
    return CompanyCatalogService(SqlAlchemyCompanyCatalogRepository(session)), session


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
            venue=None,
            offset=0,
            limit=5000,
        )
    finally:
        session.close()

    company = next(row for row in response.companies if row.ticker == "FPT")
    assert company.model_dump() == {
        "instrument_id": instrument.id,
        "ticker": "FPT",
        "company_name": "FPT Corporation",
        "country_code": "VN",
        "sector": "Information Technology",
        "industry": "Công nghệ và thông tin",
        "venue_code": "HOSE",
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
        "instrument_id", "ticker", "company_name", "country_code", "sector",
        "industry", "venue_code",
        "lists", "first_session", "last_session", "stored_sessions",
    }


def test_company_catalog_groups_multiple_instruments_under_one_issuer():
    service, session = _catalog_service()
    try:
        response = list_company_catalog(
            service,
            country="US",
            search="Alphabet",
            sector=None,
            offset=0,
            limit=5000,
        )
    finally:
        session.close()

    assert response.total == 1
    alphabet = response.companies[0]
    assert alphabet.display_name == "Alphabet Inc."
    assert {instrument.ticker for instrument in alphabet.instruments} == {
        "GOOG", "GOOGL",
    }
    assert alphabet.identifiers[0].model_dump() == {
        "namespace": "sec_cik",
        "value": "1652044",
    }
    assert all(company.instruments for company in response.companies)


def test_company_catalog_openapi_contract_is_company_centric():
    schema = app.openapi()

    operation = schema["paths"]["/companies/catalog"]["get"]
    assert operation["operationId"] == "listCompanyCatalog"
    properties = schema["components"]["schemas"]["CompanyCatalogItemResponse"][
        "properties"
    ]
    assert set(properties) == {
        "id", "display_name", "legal_name", "country_code", "sector",
        "industry", "is_active", "identifiers", "instruments",
    }


def test_company_catalog_paginates_and_returns_server_side_facets():
    service, session = _catalog_service()
    try:
        first = list_company_catalog(
            service,
            country=None,
            search=None,
            sector=None,
            offset=0,
            limit=50,
        )
        second = list_company_catalog(
            service,
            country=None,
            search=None,
            sector=None,
            offset=50,
            limit=50,
        )
    finally:
        session.close()

    assert first.total > 2700
    assert len(first.companies) == 50
    assert len(second.companies) == 50
    assert {company.id for company in first.companies}.isdisjoint(
        company.id for company in second.companies
    )
    countries = {facet.value: facet.count for facet in first.facets.countries}
    assert countries["US"] > 2000
    assert countries["VN"] > 300
    assert sum(countries.values()) == first.total


def test_instrument_list_paginates_and_returns_universe_and_sector_facets():
    service, session = _service()
    try:
        response = list_companies(
            service,
            universe="US_ALL",
            search=None,
            sector=None,
            industry=None,
            venue=None,
            offset=0,
            limit=50,
        )
    finally:
        session.close()

    assert response.total == 2472
    assert len(response.companies) == 50
    assert response.facets.all_count == 2472
    universes = {facet.value: facet.count for facet in response.facets.universes}
    assert universes["US500"] == 503
    assert universes["US2000"] == 1954
    assert sum(facet.count for facet in response.facets.sectors) == 2472
