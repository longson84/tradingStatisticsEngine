"""Add relational audit records for live Universe synchronization.

Revision ID: 0020
Revises: 0019
Create Date: 2026-08-13
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "universe_sync_runs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("universe_code", sa.String(length=16), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("received_count", sa.Integer(), nullable=False),
        sa.Column("added_count", sa.Integer(), nullable=False),
        sa.Column("removed_count", sa.Integer(), nullable=False),
        sa.Column("unchanged_count", sa.Integer(), nullable=False),
        sa.Column("error", sa.String(length=2000), nullable=True),
        sa.CheckConstraint(
            "status IN ('succeeded', 'failed')",
            name="ck_universe_sync_runs_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_universe_sync_runs_universe_started",
        "universe_sync_runs",
        ["universe_code", "started_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_universe_sync_runs_universe_started",
        table_name="universe_sync_runs",
    )
    op.drop_table("universe_sync_runs")
