"""Add reusable Data Operations batch plans and parent run history.

Revision ID: 0030
Revises: 0029
Create Date: 2026-09-04
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0030"
down_revision: str | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_data_operation_runs_scope_type", "data_operation_runs", type_="check")
    op.create_check_constraint(
        "ck_data_operation_runs_scope_type",
        "data_operation_runs",
        "scope_type IN ('category', 'universe', 'watchlist', 'instrument')",
    )
    op.create_table(
        "data_operation_batch_plans",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "data_operation_batch_steps",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("plan_id", sa.BigInteger(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("target_type", sa.String(length=16), nullable=False),
        sa.Column("target_id", sa.String(length=64), nullable=False),
        sa.Column("dataset", sa.String(length=16), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.CheckConstraint(
            "target_type IN ('category', 'universe', 'watchlist', 'instrument')",
            name="ck_data_operation_batch_steps_target_type",
        ),
        sa.CheckConstraint("dataset IN ('prices', 'fundamentals')", name="ck_data_operation_batch_steps_dataset"),
        sa.CheckConstraint("mode IN ('incremental', 'full')", name="ck_data_operation_batch_steps_mode"),
        sa.ForeignKeyConstraint(["plan_id"], ["data_operation_batch_plans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_id", "position", name="uq_data_operation_batch_step_position"),
    )
    op.create_index("ix_data_operation_batch_steps_plan_id", "data_operation_batch_steps", ["plan_id"])
    op.create_table(
        "data_operation_batch_runs",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("plan_id", sa.BigInteger(), nullable=True),
        sa.Column("plan_name", sa.String(length=100), nullable=False),
        sa.Column("step_snapshot", sa.JSON(), nullable=False),
        sa.Column("child_job_ids", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("current_step", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_steps", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.String(length=4000), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed')",
            name="ck_data_operation_batch_runs_status",
        ),
        sa.ForeignKeyConstraint(["plan_id"], ["data_operation_batch_plans.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_data_operation_batch_runs_plan_id", "data_operation_batch_runs", ["plan_id"])
    op.create_index("ix_data_operation_batch_runs_created_at", "data_operation_batch_runs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_data_operation_batch_runs_created_at", table_name="data_operation_batch_runs")
    op.drop_index("ix_data_operation_batch_runs_plan_id", table_name="data_operation_batch_runs")
    op.drop_table("data_operation_batch_runs")
    op.drop_index("ix_data_operation_batch_steps_plan_id", table_name="data_operation_batch_steps")
    op.drop_table("data_operation_batch_steps")
    op.drop_table("data_operation_batch_plans")
    op.drop_constraint("ck_data_operation_runs_scope_type", "data_operation_runs", type_="check")
    op.create_check_constraint(
        "ck_data_operation_runs_scope_type",
        "data_operation_runs",
        "scope_type IN ('universe', 'watchlist', 'instrument')",
    )
