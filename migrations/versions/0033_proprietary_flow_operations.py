"""Allow proprietary-flow Data Operations.

Revision ID: 0033
Revises: 0032
Create Date: 2026-10-18
"""
from typing import Sequence

from alembic import op


revision: str = "0033"
down_revision: str | None = "0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    _replace_dataset_checks(include_proprietary_flow=True)


def downgrade() -> None:
    _replace_dataset_checks(include_proprietary_flow=False)


def _replace_dataset_checks(*, include_proprietary_flow: bool) -> None:
    values = "'prices', 'fundamentals', 'foreign_flow'"
    if include_proprietary_flow:
        values += ", 'proprietary_flow'"
    for name, table in (
        ("ck_data_operation_runs_dataset", "data_operation_runs"),
        ("ck_data_operation_batch_steps_dataset", "data_operation_batch_steps"),
    ):
        op.drop_constraint(name, table, type_="check")
        op.create_check_constraint(name, table, f"dataset IN ({values})")
