"""Allow period-aware session-statistics Data Operations.

Revision ID: 0035
Revises: 0034
Create Date: 2026-10-18
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0035"
down_revision: str | None = "0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("data_operation_runs", sa.Column("period_start", sa.Date()))
    op.add_column("data_operation_runs", sa.Column("period_end", sa.Date()))
    _replace_run_dataset_check(include_session_stats=True)


def downgrade() -> None:
    _replace_run_dataset_check(include_session_stats=False)
    op.drop_column("data_operation_runs", "period_end")
    op.drop_column("data_operation_runs", "period_start")


def _replace_run_dataset_check(*, include_session_stats: bool) -> None:
    values = "'prices', 'fundamentals', 'foreign_flow', 'proprietary_flow'"
    if include_session_stats:
        values += ", 'session_stats'"
    op.drop_constraint(
        "ck_data_operation_runs_dataset", "data_operation_runs", type_="check"
    )
    op.create_check_constraint(
        "ck_data_operation_runs_dataset",
        "data_operation_runs",
        f"dataset IN ({values})",
    )
