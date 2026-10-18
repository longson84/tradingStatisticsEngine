"""Allow exact-period daily trade-history Data Operations.

Revision ID: 0038
Revises: 0037
Create Date: 2026-10-18
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0038"
down_revision: str | None = "0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    _replace_run_dataset_check(include_trade_history=True)


def downgrade() -> None:
    # These audit rows belong to the removed dataset; preserve all other runs.
    op.execute(sa.text("DELETE FROM data_operation_runs WHERE dataset = 'trade_history'"))
    _replace_run_dataset_check(include_trade_history=False)


def _replace_run_dataset_check(*, include_trade_history: bool) -> None:
    values = "'prices', 'fundamentals', 'foreign_flow', 'proprietary_flow', 'session_stats'"
    if include_trade_history:
        values += ", 'trade_history'"
    op.drop_constraint(
        "ck_data_operation_runs_dataset", "data_operation_runs", type_="check"
    )
    op.create_check_constraint(
        "ck_data_operation_runs_dataset",
        "data_operation_runs",
        f"dataset IN ({values})",
    )
