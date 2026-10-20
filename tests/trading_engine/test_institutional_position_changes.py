from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from trading_engine.institutional import derive_institutional_position_changes
from trading_engine.types import InstitutionalPositionSnapshot


PERIOD = date(2026, 6, 30)
ACCEPTED = datetime(2026, 8, 14, 16, 30, tzinfo=UTC)


def snapshot(
    manager_id: int,
    shares: int,
    *,
    period: date = PERIOD,
    accepted_at: datetime = ACCEPTED,
    security_type: str = "common_stock",
) -> InstitutionalPositionSnapshot:
    return InstitutionalPositionSnapshot(
        manager_id=manager_id,
        instrument_id=101,
        report_period=period,
        accepted_at=accepted_at,
        shares=Decimal(shares),
        security_type=security_type,
    )


def test_derives_new_added_unchanged_reduced_and_exited_positions() -> None:
    previous_period = date(2026, 3, 31)
    previous = (
        snapshot(2, 100, period=previous_period),
        snapshot(3, 100, period=previous_period),
        snapshot(4, 100, period=previous_period),
        snapshot(5, 100, period=previous_period),
    )
    current = (
        snapshot(1, 50),
        snapshot(2, 125),
        snapshot(3, 100),
        snapshot(4, 40),
    )

    result = derive_institutional_position_changes(
        previous,
        current,
        current_report_period=PERIOD,
        current_filing_accepted_at={5: ACCEPTED},
    )

    assert [change.manager_id for change in result] == [1, 2, 3, 4, 5]
    assert [change.action for change in result] == [
        "new", "added", "unchanged", "reduced", "exited",
    ]
    assert [change.share_change for change in result] == [
        Decimal("50"), Decimal("25"), Decimal("0"), Decimal("-60"), Decimal("-100"),
    ]
    assert [change.percentage_change for change in result] == [
        None, Decimal("25"), Decimal("0"), Decimal("-60"), None,
    ]
    assert result[-1].current_shares == Decimal("0")
    assert all(change.formula_version == "institutional_position_change_v1" for change in result)
    assert all(change.available_at == ACCEPTED for change in result)


def test_does_not_infer_exit_without_a_current_filing_for_the_manager() -> None:
    result = derive_institutional_position_changes(
        (snapshot(1, 100, period=date(2026, 3, 31)),),
        (),
        current_report_period=PERIOD,
        current_filing_accepted_at={},
    )

    assert result == ()


def test_excludes_put_and_call_positions_from_common_stock_changes() -> None:
    result = derive_institutional_position_changes(
        (),
        (snapshot(1, 10, security_type="put"), snapshot(2, 20, security_type="call")),
        current_report_period=PERIOD,
        current_filing_accepted_at={},
    )

    assert result == ()


@pytest.mark.parametrize("shares", [0, -1])
def test_rejects_non_positive_reported_shares(shares: int) -> None:
    with pytest.raises(ValueError, match="shares must be positive"):
        derive_institutional_position_changes(
            (),
            (snapshot(1, shares),),
            current_report_period=PERIOD,
            current_filing_accepted_at={},
        )


def test_rejects_duplicate_manager_instrument_period_identity() -> None:
    with pytest.raises(ValueError, match="duplicate institutional position"):
        derive_institutional_position_changes(
            (),
            (snapshot(1, 10), snapshot(1, 20)),
            current_report_period=PERIOD,
            current_filing_accepted_at={},
        )


def test_requires_timezone_aware_acceptance_for_point_in_time_availability() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        derive_institutional_position_changes(
            (),
            (snapshot(1, 10, accepted_at=datetime(2026, 8, 14, 16, 30)),),
            current_report_period=PERIOD,
            current_filing_accepted_at={},
        )


def test_requires_positions_to_match_the_requested_current_period() -> None:
    with pytest.raises(ValueError, match="current_report_period"):
        derive_institutional_position_changes(
            (),
            (snapshot(1, 10, period=date(2026, 3, 31)),),
            current_report_period=PERIOD,
            current_filing_accepted_at={},
        )
