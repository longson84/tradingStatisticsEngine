"""Add immutable Instrument session-statistics snapshots.

Revision ID: 0034
Revises: 0033
Create Date: 2026-10-18
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0034"
down_revision: str | None = "0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "instrument_session_stat_snapshots",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("instrument_id", sa.BigInteger(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "period_start <= period_end",
            name="ck_instrument_session_stat_snapshots_period",
        ),
        sa.CheckConstraint(
            "schema_version > 0",
            name="ck_instrument_session_stat_snapshots_schema_version",
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"], ["instruments.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_instrument_session_stat_snapshots_instrument_id",
        "instrument_session_stat_snapshots",
        ["instrument_id"],
    )
    op.create_index(
        "ix_instrument_session_stat_snapshot_lookup",
        "instrument_session_stat_snapshots",
        ["instrument_id", "period_start", "period_end", "fetched_at"],
    )
    op.create_table(
        "instrument_session_stat_metrics",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("snapshot_id", sa.BigInteger(), nullable=False),
        sa.Column("metric_code", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Numeric(38, 6), nullable=False),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["instrument_session_stat_snapshots.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "snapshot_id", "metric_code",
            name="uq_instrument_session_stat_metric_identity",
        ),
    )
    op.create_index(
        "ix_instrument_session_stat_metrics_snapshot_id",
        "instrument_session_stat_metrics",
        ["snapshot_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_instrument_session_stat_metrics_snapshot_id",
        table_name="instrument_session_stat_metrics",
    )
    op.drop_table("instrument_session_stat_metrics")
    op.drop_index(
        "ix_instrument_session_stat_snapshot_lookup",
        table_name="instrument_session_stat_snapshots",
    )
    op.drop_index(
        "ix_instrument_session_stat_snapshots_instrument_id",
        table_name="instrument_session_stat_snapshots",
    )
    op.drop_table("instrument_session_stat_snapshots")
