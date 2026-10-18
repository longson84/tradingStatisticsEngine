"""Enforce immutable session-statistics snapshot identity.

Revision ID: 0036
Revises: 0035
Create Date: 2026-10-18
"""
from typing import Sequence

from alembic import op


revision: str = "0036"
down_revision: str | None = "0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_instrument_session_stat_snapshot_identity",
        "instrument_session_stat_snapshots",
        ["instrument_id", "period_start", "period_end", "source", "fetched_at"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_instrument_session_stat_snapshot_identity",
        "instrument_session_stat_snapshots",
        type_="unique",
    )
