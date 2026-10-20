"""Versioned changes inferred from consecutive institutional holdings."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal

from trading_engine.types import (
    InstitutionalPositionAction,
    InstitutionalPositionChange,
    InstitutionalPositionSnapshot,
)


FORMULA_VERSION = "institutional_position_change_v1"


def derive_institutional_position_changes(
    previous_positions: tuple[InstitutionalPositionSnapshot, ...],
    current_positions: tuple[InstitutionalPositionSnapshot, ...],
    *,
    current_report_period: date,
    current_filing_accepted_at: Mapping[int, datetime],
) -> tuple[InstitutionalPositionChange, ...]:
    """Compare common-stock positions after proving each current filing exists.

    `current_filing_accepted_at` is required for inferred exits because an absent
    holding is meaningful only when that manager filed for the current period.
    """
    previous = _common_positions(previous_positions, before=current_report_period)
    current = _common_positions(current_positions, at=current_report_period)
    _validate_acceptance_map(current_filing_accepted_at)

    changes: list[InstitutionalPositionChange] = []
    for key in sorted(previous.keys() | current.keys(), key=lambda item: (item[1], item[0])):
        manager_id, instrument_id = key
        prior = previous.get(key)
        present = current.get(key)
        if present is None and manager_id not in current_filing_accepted_at:
            continue

        previous_shares = prior.shares if prior is not None else Decimal(0)
        current_shares = present.shares if present is not None else Decimal(0)
        delta = current_shares - previous_shares
        action = _action(previous_shares, current_shares)
        percentage = (
            None
            if action in {"new", "exited"}
            else delta / previous_shares * Decimal(100)
        )
        changes.append(InstitutionalPositionChange(
            manager_id=manager_id,
            instrument_id=instrument_id,
            report_period=current_report_period,
            available_at=(
                present.accepted_at
                if present is not None
                else current_filing_accepted_at[manager_id]
            ),
            previous_shares=previous_shares,
            current_shares=current_shares,
            share_change=delta,
            percentage_change=percentage,
            action=action,
            formula_version=FORMULA_VERSION,
        ))
    return tuple(changes)


def _common_positions(
    positions: tuple[InstitutionalPositionSnapshot, ...],
    *,
    at: date | None = None,
    before: date | None = None,
) -> dict[tuple[int, int], InstitutionalPositionSnapshot]:
    result: dict[tuple[int, int], InstitutionalPositionSnapshot] = {}
    for position in positions:
        if position.shares <= 0:
            raise ValueError("institutional position shares must be positive")
        if position.accepted_at.tzinfo is None:
            raise ValueError("institutional position accepted_at must be timezone-aware")
        if at is not None and position.report_period != at:
            raise ValueError("current position does not match current_report_period")
        if before is not None and position.report_period >= before:
            raise ValueError("previous position must precede current_report_period")
        if position.security_type != "common_stock":
            continue
        key = (position.manager_id, position.instrument_id)
        if key in result:
            raise ValueError("duplicate institutional position identity")
        result[key] = position
    return result


def _validate_acceptance_map(values: Mapping[int, datetime]) -> None:
    if any(value.tzinfo is None for value in values.values()):
        raise ValueError("current filing accepted_at must be timezone-aware")


def _action(previous: Decimal, current: Decimal) -> InstitutionalPositionAction:
    if previous == 0:
        return "new"
    if current == 0:
        return "exited"
    if current > previous:
        return "added"
    if current < previous:
        return "reduced"
    return "unchanged"
