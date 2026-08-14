from __future__ import annotations

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from api.db.models import Base, Company
from api.main import app
from api.repositories.sqlalchemy_company_catalog_repository import (
    SqlAlchemyCompanyCatalogRepository,
)
from api.repositories.sqlalchemy_instrument_analysis_repository import (
    SqlAlchemyInstrumentAnalysisRepository,
)
from api.repositories.sqlalchemy_instrument_routing_repository import (
    SqlAlchemyInstrumentRoutingRepository,
)
from api.routes.companies import list_companies
from api.routes.instruments import list_instruments
from api.services.company_catalog_service import CompanyCatalogService
from api.services.instrument_analysis_service import InstrumentAnalysisService
from tests.api.catalog_seed import seed_company_catalog


def _services() -> tuple[CompanyCatalogService, InstrumentAnalysisService, Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    seed_company_catalog(session)
    return (
        CompanyCatalogService(SqlAlchemyCompanyCatalogRepository(session)),
        InstrumentAnalysisService(
            SqlAlchemyInstrumentAnalysisRepository(session),
            SqlAlchemyInstrumentRoutingRepository(session),
        ),
        session,
    )


def test_root_company_catalog_groups_alphabet_share_classes_under_one_issuer():
    company_service, _, session = _services()
    try:
        response = list_companies(
            company_service,
            listing_country="US",
            search="Alphabet",
            sector=None,
            offset=0,
            limit=50,
        )
    finally:
        session.close()

    assert response.total == 1
    alphabet = response.companies[0]
    assert alphabet.display_name == "Alphabet Inc."
    assert {instrument.symbol for instrument in alphabet.instruments} == {
        "GOOG",
        "GOOGL",
    }
    assert alphabet.identifiers[0].model_dump() == {
        "namespace": "sec_cik",
        "value": "1652044",
    }
    assert alphabet.domicile_country_code == "US"
    assert alphabet.listing_country_codes == ["US"]


def test_company_catalog_uses_server_pagination_and_facets():
    company_service, _, session = _services()
    try:
        first = list_companies(
            company_service,
            listing_country=None,
            search=None,
            sector=None,
            offset=0,
            limit=50,
        )
        second = list_companies(
            company_service,
            listing_country=None,
            search=None,
            sector=None,
            offset=50,
            limit=50,
        )
    finally:
        session.close()

    assert first.total == 65
    assert len(first.companies) == 50
    assert len(second.companies) == 15
    assert {row.id for row in first.companies}.isdisjoint(
        row.id for row in second.companies
    )
    countries = {
        row.value: row.count
        for row in first.facets.listing_countries
    }
    assert countries == {"US": 59, "VN": 6}
    assert sum(countries.values()) == first.total


def test_company_domicile_is_independent_from_listing_country():
    company_service, _, session = _services()
    try:
        apple = session.scalar(
            select(Company).where(Company.display_name == "Apple Inc.")
        )
        assert apple is not None
        apple.domicile_country_code = "CA"
        session.commit()

        response = list_companies(
            company_service,
            listing_country="US",
            search="Apple",
            sector=None,
            offset=0,
            limit=50,
        )
    finally:
        session.close()

    assert response.total == 1
    assert response.companies[0].domicile_country_code == "CA"
    assert response.companies[0].listing_country_codes == ["US"]


def test_instrument_catalog_supports_all_equities_and_real_universe_filters():
    _, instrument_service, session = _services()
    try:
        all_equities = list_instruments(
            instrument_service,
            scope="equity",
            universe=None,
            search="AAPL",
            sector=None,
            industry=None,
            venue=None,
            has_price_history=False,
            offset=0,
            limit=50,
        )
        us500 = list_instruments(
            instrument_service,
            scope="equity",
            universe="US500",
            search="AAPL",
            sector=None,
            industry=None,
            venue=None,
            has_price_history=False,
            offset=0,
            limit=50,
        )
    finally:
        session.close()

    assert all_equities.total == 1
    assert us500.total == 1
    instrument = all_equities.instruments[0]
    assert instrument.symbol == "AAPL"
    assert instrument.sector == "Information Technology"
    assert instrument.industry == "Technology Hardware, Storage & Peripherals"
    assert instrument.universes == ["US100", "US30", "US500"]
    assert all_equities.facets.all_count == 1
    assert all_equities.facets.sectors[0].value == "Information Technology"


def test_openapi_exposes_three_precise_catalogs_without_company_compatibility_paths():
    schema = app.openapi()

    assert schema["paths"]["/companies"]["get"]["operationId"] == "listCompanies"
    company_parameters = {
        parameter["name"]
        for parameter in schema["paths"]["/companies"]["get"]["parameters"]
    }
    assert "listing_country" in company_parameters
    assert "country" not in company_parameters
    assert schema["paths"]["/instruments"]["get"]["operationId"] == "listInstruments"
    assert schema["paths"]["/universes"]["get"]["operationId"] == "listUniverses"
    assert "/companies/catalog" not in schema["paths"]
    assert "/companies/universes" not in schema["paths"]
    components = schema["components"]["schemas"]
    assert "CompanyListResponse" not in components
    assert "CompanyUniversesResponse" not in components
    assert "CompanyUniverseResponse" not in components
    assert "US_ALL" not in str(schema)
    assert "VN_ALL" not in str(schema)

    company_fields = components["CompanyCatalogItemResponse"]["properties"]
    assert {
        "id",
        "display_name",
        "domicile_country_code",
        "listing_country_codes",
        "identifiers",
        "instruments",
    } <= company_fields.keys()
    assert "country_code" not in company_fields
    company_instrument_fields = components["CompanyInstrumentResponse"]["properties"]
    assert "symbol" in company_instrument_fields
    assert "ticker" not in company_instrument_fields
    instrument_fields = components["InstrumentCatalogItemResponse"]["properties"]
    assert {"id", "symbol", "sector", "industry", "universes"} <= instrument_fields.keys()
