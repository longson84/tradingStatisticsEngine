from datetime import UTC, date, datetime
from decimal import Decimal

from api.repositories.institutional_activity_repository import (
    InstitutionalActivityInstrument,
    InstitutionalFilingMetadata,
    InstitutionalManagerRecord,
)
from api.services.institutional_activity_service import InstitutionalActivityService
from trading_engine.types import InstitutionalPositionSnapshot


PERIODS = (date(2026, 6, 30), date(2026, 3, 31))
ACCEPTED = datetime(2026, 8, 14, 16, 30, tzinfo=UTC)


class Repository:
    def __init__(self):
        self.instrument = InstitutionalActivityInstrument(
            42, "AAPL", "common_stock", "NASDAQ", "US", True,
        )
        self.identifier = "037833100"
        self.periods = PERIODS
        self.positions = {
            PERIODS[1]: (
                InstitutionalPositionSnapshot(1, 42, PERIODS[1], ACCEPTED, Decimal("100"), "common_stock"),
                InstitutionalPositionSnapshot(2, 42, PERIODS[1], ACCEPTED, Decimal("50"), "common_stock"),
            ),
            PERIODS[0]: (
                InstitutionalPositionSnapshot(1, 42, PERIODS[0], ACCEPTED, Decimal("125"), "common_stock"),
                InstitutionalPositionSnapshot(3, 42, PERIODS[0], ACCEPTED, Decimal("75"), "common_stock"),
            ),
        }

    def get_instrument(self, instrument_id):
        return self.instrument if instrument_id == 42 else None

    def get_effective_identifier(self, instrument_id, namespace, on):
        return self.identifier

    def list_report_periods(self, instrument_id, limit):
        return self.periods[:limit]

    def list_effective_common_stock_positions(self, instrument_id, report_period):
        return self.positions[report_period]

    def list_filing_acceptance(self, manager_ids, report_period):
        return {manager_id: ACCEPTED for manager_id in manager_ids}

    def list_managers(self, manager_ids):
        names = {1: "Berkshire Hathaway", 2: "Exited Capital", 3: "New Fund"}
        return {manager_id: InstitutionalManagerRecord(
            manager_id, str(manager_id).zfill(10), names[manager_id], manager_id == 1,
        ) for manager_id in manager_ids}

    def list_effective_filing_metadata(self, manager_ids, report_period, instrument_id):
        return {manager_id: InstitutionalFilingMetadata(
            manager_id, report_period, ACCEPTED, "accepted_at",
            f"https://www.sec.gov/filing/{manager_id}",
        ) for manager_id in manager_ids}


def test_service_builds_history_latest_changes_and_current_holders_from_storage() -> None:
    result = InstitutionalActivityService(Repository()).get_activity(42, quarters=8)

    assert result.status == "available"
    assert result.latest_report_period == PERIODS[0]
    assert [(row.report_period, row.holder_count, row.total_shares) for row in result.history] == [
        (PERIODS[1], 2, Decimal("150")),
        (PERIODS[0], 2, Decimal("200")),
    ]
    assert [(row.manager_name, row.action) for row in result.changes] == [
        ("Berkshire Hathaway", "added"),
        ("Exited Capital", "exited"),
        ("New Fund", "new"),
    ]
    assert result.action_counts == {
        "new": 1, "added": 1, "unchanged": 0, "reduced": 0, "exited": 1,
    }
    assert [(row.manager_name, row.shares) for row in result.current_holders] == [
        ("Berkshire Hathaway", Decimal("125")),
        ("New Fund", Decimal("75")),
    ]
    assert all(row.source_url.startswith("https://www.sec.gov/") for row in result.changes)
    assert result.formula_version == "institutional_position_change_v1"


def test_latest_availability_includes_a_zero_holder_exit_disclosure() -> None:
    repository = Repository()
    exit_accepted = datetime(2026, 8, 20, 12, tzinfo=UTC)
    repository.positions[PERIODS[0]] = ()
    repository.list_filing_acceptance = lambda manager_ids, report_period: {
        manager_id: exit_accepted for manager_id in manager_ids
    }
    repository.list_effective_filing_metadata = (
        lambda manager_ids, report_period, instrument_id: {
            manager_id: InstitutionalFilingMetadata(
                manager_id, report_period, exit_accepted, "accepted_at",
                f"https://www.sec.gov/filing/{manager_id}",
            )
            for manager_id in manager_ids
        }
    )

    result = InstitutionalActivityService(repository).get_activity(42)

    assert result.latest_available_at == exit_accepted


def test_service_returns_explicit_known_instrument_unavailability_states() -> None:
    repository = Repository()
    repository.instrument = InstitutionalActivityInstrument(
        42, "FPT", "common_stock", "HOSE", "VN", True,
    )
    result = InstitutionalActivityService(repository).get_activity(42)
    assert result.status == "unsupported_instrument"
    assert result.history == ()

    repository.instrument = InstitutionalActivityInstrument(
        42, "AAPL", "common_stock", "NASDAQ", "US", True,
    )
    repository.identifier = None
    result = InstitutionalActivityService(repository).get_activity(42)
    assert result.status == "missing_identifier"

    repository.identifier = "037833100"
    repository.periods = ()
    result = InstitutionalActivityService(repository).get_activity(42)
    assert result.status == "no_stored_filings"


def test_service_returns_unknown_instrument_separately() -> None:
    result = InstitutionalActivityService(Repository()).get_activity(999)
    assert result.status == "unknown_instrument"
