from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from api.db.models import Base, Company, Instrument, InstrumentSymbol, Venue
from api.providers.nasdaq_symbol_directory import (
    USListingVenue,
    USListingVenueCatalog,
    _parse_nasdaq_listed,
    _parse_other_listed,
)
from api.repositories.equity_venue_repository import (
    EquityVenueAssignment,
    EquityVenueInstrumentRecord,
)
from api.repositories.sqlalchemy_equity_venue_repository import (
    SqlAlchemyEquityVenueRepository,
)
from api.services.equity_venue_service import EquityVenueService


class FakeRepository:
    def __init__(self, instruments: tuple[EquityVenueInstrumentRecord, ...]) -> None:
        self.instruments = instruments
        self.registry_ensured = False
        self.assignments: tuple[EquityVenueAssignment, ...] = ()

    def ensure_venue_registry(self) -> None:
        self.registry_ensured = True

    def list_us_equity_instruments(self):
        return self.instruments

    def assign_venues(self, assignments):
        self.assignments = assignments
        return len(assignments)


def test_nasdaq_symbol_directory_parsers_preserve_listing_venue():
    nasdaq = _parse_nasdaq_listed(
        "Symbol|Security Name|Market Category|Test Issue|Financial Status|"
        "Round Lot Size|ETF|NextShares\n"
        "MSFT|Microsoft Corporation|Q|N|N|100|N|N\n"
        "TEST|Test issue|Q|Y|N|100|N|N\n"
        "File Creation Time: 0811202617:00|||||||\n"
    )
    other = _parse_other_listed(
        "ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|"
        "Test Issue|NASDAQ Symbol\n"
        "BRK B|Berkshire Hathaway|N|BRK.B|N|100|N|BRK-B\n"
        "SHOP|Shopify|Z|SHOP|N|100|N|SHOP\n"
    )

    assert nasdaq == (USListingVenue(
        primary_symbols=("MSFT",),
        alternate_symbols=(),
        venue_code="NASDAQ",
    ),)
    assert other == (
        USListingVenue(
            primary_symbols=("BRK B", "BRK-B"),
            alternate_symbols=("BRK.B",),
            venue_code="NYSE",
        ),
        USListingVenue(
            primary_symbols=("SHOP",),
            alternate_symbols=(),
            venue_code="CBOE_BZX",
        ),
    )


def test_equity_venue_sync_matches_aliases_and_rejects_ambiguous_symbols():
    repository = FakeRepository((
        EquityVenueInstrumentRecord(1, "MSFT", (), None),
        EquityVenueInstrumentRecord(2, "BRK-B", ("BRK.B",), "NYSE"),
        EquityVenueInstrumentRecord(3, "DUP", (), None),
        EquityVenueInstrumentRecord(4, "MISSING", (), None),
    ))
    catalog = USListingVenueCatalog(
        listings=(
            USListingVenue(("MSFT",), (), "NASDAQ"),
            USListingVenue(("BRK B",), (), "NYSE"),
            USListingVenue(("DUP",), (), "NYSE"),
            USListingVenue(("DUP",), (), "NASDAQ"),
        ),
        fetched_at=datetime(2026, 8, 11, 17, tzinfo=UTC),
    )

    result = EquityVenueService(repository).sync_us_listing_venues(catalog)

    assert repository.registry_ensured is True
    assert repository.assignments == (EquityVenueAssignment(1, "NASDAQ"),)
    assert result.matched_instruments == 2
    assert result.updated_instruments == 1
    assert result.unchanged_instruments == 1
    assert result.unresolved_symbols == ("MISSING",)
    assert result.ambiguous_symbols == ("DUP",)


def test_sqlalchemy_repository_creates_registry_and_assigns_exact_instrument():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session, session.begin():
        repository = SqlAlchemyEquityVenueRepository(session)
        repository.ensure_venue_registry()
        session.flush()
        nasdaq = session.scalar(select(Venue).where(Venue.code == "NASDAQ"))
        assert nasdaq is not None
        instrument = Instrument(
            company=Company(
                display_name="Example Issuer",
                domicile_country_code="CA",
                source="test",
            ),
            venue=nasdaq,
            symbol="EXAMPLE",
            currency="USD",
            source="test",
        )
        instrument.symbols.append(InstrumentSymbol(
            namespace="listing",
            symbol="EXAMPLE.A",
            is_primary=True,
            source="test",
        ))
        session.add(instrument)
        session.flush()

        rows = repository.list_us_equity_instruments()
        assert rows == (EquityVenueInstrumentRecord(
            instrument_id=instrument.id,
            symbol="EXAMPLE",
            symbol_aliases=("EXAMPLE.A",),
            venue_code="NASDAQ",
        ),)
        assert repository.assign_venues((
            EquityVenueAssignment(instrument.id, "NYSE"),
        )) == 1

    with Session(engine) as session:
        stored = session.scalar(
            select(Instrument).where(Instrument.symbol == "EXAMPLE")
        )
        assert stored is not None and stored.venue is not None
        assert stored.venue.code == "NYSE"
        assert stored.venue.timezone_name == "America/New_York"
        assert stored.venue.trading_calendar_code == "US_EQUITIES"
        assert stored.venue.session_cutoff_time.isoformat() == "16:15:00"
