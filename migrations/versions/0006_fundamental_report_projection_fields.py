"""Preserve legacy period labels and provider methodology.

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-03
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "fundamental_reports",
        sa.Column("period_label", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "fundamental_reports",
        sa.Column("methodology", sa.String(length=1000), nullable=True),
    )
    op.execute("""
        UPDATE fundamental_reports
        SET period_label = NULLIF(split_part(report_key, ':', 4), '-')
        WHERE report_key LIKE 'legacy:%'
    """)
    op.execute("""
        UPDATE fundamental_reports
        SET methodology = CASE
            WHEN source = 'yfinance'
                THEN 'Yahoo reported EPS plus quarterly income and balance sheet, effective next day'
            WHEN source = 'vnstock-vci-4.0.5'
                THEN 'VCI quarterly RATIO_TTM aligned to day after financial-report publicDate'
            ELSE NULL
        END
    """)


def downgrade() -> None:
    op.drop_column("fundamental_reports", "methodology")
    op.drop_column("fundamental_reports", "period_label")
