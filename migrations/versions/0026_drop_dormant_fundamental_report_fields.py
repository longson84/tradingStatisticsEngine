"""Drop unpopulated fundamental-report metadata fields.

Revision ID: 0026
Revises: 0025
Create Date: 2026-08-13
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_fundamental_reports_scope",
        "fundamental_reports",
        type_="check",
    )
    op.drop_column("fundamental_reports", "is_restatement")
    op.drop_column("fundamental_reports", "scope")
    op.drop_column("fundamental_reports", "published_at")
    op.drop_column("fundamental_reports", "provider_report_id")


def downgrade() -> None:
    op.add_column(
        "fundamental_reports",
        sa.Column("provider_report_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "fundamental_reports",
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "fundamental_reports",
        sa.Column(
            "scope",
            sa.String(length=16),
            nullable=False,
            server_default="unknown",
        ),
    )
    op.add_column(
        "fundamental_reports",
        sa.Column(
            "is_restatement",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.create_check_constraint(
        "ck_fundamental_reports_scope",
        "fundamental_reports",
        "scope IN ('consolidated', 'standalone', 'unknown')",
    )
    op.alter_column("fundamental_reports", "scope", server_default=None)
    op.alter_column("fundamental_reports", "is_restatement", server_default=None)
