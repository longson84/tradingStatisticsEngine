from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from api.db.models import Base, Instrument
from api.repositories.institutional_activity_repository import (
    InstitutionalFilingWrite,
    InstitutionalManagerWrite,
    InstitutionalPositionWrite,
    InstrumentIdentifierWrite,
)
from api.repositories.sqlalchemy_institutional_activity_repository import (
    SqlAlchemyInstitutionalActivityRepository,
)


PERIOD = date(2026, 6, 30)
FETCHED = datetime(2026, 8, 15, 3, tzinfo=UTC)


@pytest.fixture
def database():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        instrument = Instrument(symbol="AAPL", currency="USD", source="test")
        session.add(instrument)
        session.commit()
        yield session, instrument.id, SqlAlchemyInstitutionalActivityRepository(session)
    engine.dispose()


def manager(cik: str, name: str) -> InstitutionalManagerWrite:
    return InstitutionalManagerWrite(sec_cik=cik, legal_name=name, source="sec-13f")


def filing(manager_id: int, accession: str, accepted_hour: int, **overrides):
    values = dict(
        manager_id=manager_id,
        accession_number=accession,
        form_type="13F-HR",
        report_period=PERIOD,
        filed_at=date(2026, 8, 14),
        accepted_at=datetime(2026, 8, 14, accepted_hour, tzinfo=UTC),
        amendment_type=None,
        amendment_number=0,
        source_url=f"https://www.sec.gov/Archives/{accession}",
        source="sec-13f",
        fetched_at=FETCHED,
    )
    return InstitutionalFilingWrite(**(values | overrides))


def position(filing_id: int, instrument_id: int | None, row: int, shares: str, **overrides):
    values = dict(
        filing_id=filing_id,
        source_row_number=row,
        instrument_id=instrument_id,
        mapping_status="mapped" if instrument_id is not None else "unmapped",
        raw_cusip="037833100",
        issuer_name="APPLE INC",
        title_of_class="COM",
        reported_value=Decimal("1000000"),
        shares=Decimal(shares),
        share_type="SH",
        put_call=None,
        investment_discretion="SOLE",
        voting_sole=Decimal(shares),
        voting_shared=Decimal("0"),
        voting_none=Decimal("0"),
        source="sec-13f",
        fetched_at=FETCHED,
    )
    return InstitutionalPositionWrite(**(values | overrides))


def test_verified_effective_identifier_lookup_never_uses_name_similarity(database):
    _, instrument_id, repository = database
    repository.add_identifier(InstrumentIdentifierWrite(
        instrument_id=instrument_id,
        namespace="cusip",
        value="037833100",
        valid_from=date(2020, 1, 1),
        valid_to=None,
        source="manual-verified",
        verified_at=FETCHED,
    ))

    assert repository.resolve_instrument_id("cusip", "037833100", PERIOD) == instrument_id
    assert repository.resolve_instrument_id("cusip", "APPLE INC", PERIOD) is None


def test_effective_positions_use_latest_restatement_and_exclude_options(database):
    session, instrument_id, repository = database
    manager_id = repository.upsert_manager(manager("0001067983", "Berkshire Hathaway"))
    original_id = repository.add_filing(filing(manager_id, "0001", 10))
    amended_id = repository.add_filing(filing(
        manager_id, "0002", 12, form_type="13F-HR/A", amendment_type="restatement"
    ))
    repository.add_positions([
        position(original_id, instrument_id, 1, "100"),
        position(amended_id, instrument_id, 1, "80"),
        position(amended_id, instrument_id, 2, "20", put_call="CALL"),
    ])
    session.commit()

    rows = repository.list_effective_common_stock_positions(instrument_id, PERIOD)

    assert len(rows) == 1
    assert rows[0].manager_id == manager_id
    assert rows[0].shares == Decimal("80")
    assert rows[0].accepted_at == datetime(2026, 8, 14, 12, tzinfo=UTC)
    assert repository.list_report_periods(instrument_id, limit=8) == (PERIOD,)


def test_same_day_amendment_sequence_deterministically_supersedes_original(database):
    session, instrument_id, repository = database
    manager_id = repository.upsert_manager(manager("0001067983", "Berkshire Hathaway"))
    original_id = repository.add_filing(filing(manager_id, "0001", 10))
    amended_id = repository.add_filing(filing(
        manager_id, "0002", 10, form_type="13F-HR/A",
        amendment_type="restatement", amendment_number=1,
    ))
    additive_id = repository.add_filing(filing(
        manager_id, "0003", 10, form_type="13F-HR/A",
        amendment_type="new_holdings", amendment_number=2,
    ))
    repository.add_positions([
        position(original_id, instrument_id, 1, "100"),
        position(amended_id, instrument_id, 1, "80"),
        position(additive_id, instrument_id, 1, "5"),
    ])
    session.commit()

    rows = repository.list_effective_common_stock_positions(instrument_id, PERIOD)

    assert rows[0].shares == Decimal("85")


def test_effective_metadata_links_to_the_filing_that_contributed_the_instrument(database):
    session, instrument_id, repository = database
    manager_id = repository.upsert_manager(manager("0001067983", "Berkshire Hathaway"))
    base_id = repository.add_filing(filing(manager_id, "base", 10))
    unrelated_id = repository.add_filing(filing(
        manager_id, "unrelated", 12, form_type="13F-HR/A",
        amendment_type="new_holdings", amendment_number=1,
    ))
    repository.add_positions([
        position(base_id, instrument_id, 1, "100"),
        position(unrelated_id, None, 1, "50", raw_cusip="594918104"),
    ])
    session.commit()

    metadata = repository.list_effective_filing_metadata(
        (manager_id,), PERIOD, instrument_id,
    )

    assert metadata[manager_id].source_url.endswith("/base")


def test_report_periods_include_later_zero_holding_filings_from_prior_holders(database):
    session, instrument_id, repository = database
    manager_id = repository.upsert_manager(manager("0001350694", "Bridgewater"))
    prior = date(2026, 3, 31)
    prior_id = repository.add_filing(filing(
        manager_id, "0001", 10, report_period=prior,
    ))
    repository.add_positions([position(prior_id, instrument_id, 1, "100")])
    repository.add_filing(filing(manager_id, "0002", 10))
    session.commit()

    assert repository.list_report_periods(instrument_id, 8) == (PERIOD, prior)


def test_current_filing_acceptance_proves_exit_without_a_position(database):
    session, _, repository = database
    manager_id = repository.upsert_manager(manager("0001350694", "Bridgewater"))
    repository.add_filing(filing(manager_id, "0003", 11))
    session.commit()

    assert repository.list_filing_acceptance((manager_id,), PERIOD) == {
        manager_id: datetime(2026, 8, 14, 11, tzinfo=UTC),
    }


def test_accessions_and_source_rows_are_idempotent_but_conflicts_are_rejected(database):
    session, instrument_id, repository = database
    manager_id = repository.upsert_manager(manager("0001067983", "Berkshire Hathaway"))
    filing_record = filing(manager_id, "0001", 10)
    filing_id = repository.add_filing(filing_record)
    assert repository.add_filing(filing_record) == filing_id
    assert repository.add_positions([position(filing_id, instrument_id, 1, "100")]) == 1
    assert repository.add_positions([position(filing_id, instrument_id, 1, "100")]) == 0
    session.commit()

    with pytest.raises(ValueError, match="conflicts with stored source row"):
        repository.add_positions([position(filing_id, instrument_id, 1, "101")])


def test_retry_with_a_new_fetch_time_is_idempotent(database):
    _, instrument_id, repository = database
    manager_id = repository.upsert_manager(manager("0001067983", "Berkshire Hathaway"))
    first = filing(manager_id, "0001", 10)
    filing_id = repository.add_filing(first)
    repository.add_positions([position(filing_id, instrument_id, 1, "100")])
    later = FETCHED.replace(hour=4)

    assert repository.add_filing(filing(
        manager_id, "0001", 10, fetched_at=later,
    )) == filing_id
    assert repository.add_positions([
        position(filing_id, instrument_id, 1, "100", fetched_at=later),
    ]) == 0
