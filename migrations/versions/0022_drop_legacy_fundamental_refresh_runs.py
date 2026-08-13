"""Drop unused Universe-scoped fundamental refresh history.

Revision ID: 0022
Revises: 0021
Create Date: 2026-08-13
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("fundamental_refresh_runs")


def downgrade() -> None:
    op.create_table(
        "fundamental_refresh_runs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.String(length=64), nullable=False),
        sa.Column("universe_id", sa.BigInteger(), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("provider_version", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("requested_count", sa.Integer(), nullable=False),
        sa.Column("reused_count", sa.Integer(), nullable=False),
        sa.Column("succeeded_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_summary", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('running', 'completed', 'failed')",
            name="ck_fundamental_refresh_runs_status",
        ),
        sa.CheckConstraint(
            "requested_count >= 0 AND reused_count >= 0 AND "
            "succeeded_count >= 0 AND failed_count >= 0",
            name="ck_fundamental_refresh_runs_counts",
        ),
        sa.ForeignKeyConstraint(
            ["universe_id"], ["universes.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id"),
    )
    op.create_index(
        "ix_fundamental_refresh_runs_universe_started",
        "fundamental_refresh_runs",
        ["universe_id", "started_at"],
    )
