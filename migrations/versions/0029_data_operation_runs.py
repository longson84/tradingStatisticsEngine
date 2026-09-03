"""Persist Data Operations run history.

Revision ID: 0029
Revises: 0028
Create Date: 2026-09-03
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0029"
down_revision: str | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "data_operation_runs",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("scope_type", sa.String(length=16), nullable=False),
        sa.Column("scope_id", sa.String(length=64), nullable=False),
        sa.Column("scope_name", sa.String(length=255), nullable=False),
        sa.Column("dataset", sa.String(length=16), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("adapter_keys", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("current", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("succeeded", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("message", sa.String(length=2000), nullable=False),
        sa.Column("output", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.String(length=4000), nullable=True),
        sa.CheckConstraint(
            "scope_type IN ('universe', 'watchlist', 'instrument')",
            name="ck_data_operation_runs_scope_type",
        ),
        sa.CheckConstraint(
            "dataset IN ('prices', 'fundamentals')",
            name="ck_data_operation_runs_dataset",
        ),
        sa.CheckConstraint(
            "mode IN ('incremental', 'full')",
            name="ck_data_operation_runs_mode",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed')",
            name="ck_data_operation_runs_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_data_operation_runs_created_at",
        "data_operation_runs",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_data_operation_runs_created_at",
        table_name="data_operation_runs",
    )
    op.drop_table("data_operation_runs")
