"""Migrate active Vnstock provider identity to generation 5.

Revision ID: 0031
Revises: 0030
Create Date: 2026-10-18
"""
from typing import Sequence

from alembic import op


revision: str = "0031"
down_revision: str | None = "0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        UPDATE instrument_symbols
        SET
            namespace = CASE
                WHEN namespace = 'vnstock_data' THEN 'vnstock'
                ELSE namespace
            END,
            source = CASE
                WHEN source = 'vnstock_data' THEN 'vnstock'
                ELSE source
            END
        WHERE valid_to IS NULL
          AND (namespace = 'vnstock_data' OR source = 'vnstock_data')
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE instrument_symbols
        SET
            namespace = CASE
                WHEN namespace = 'vnstock' THEN 'vnstock_data'
                ELSE namespace
            END,
            source = CASE
                WHEN source = 'vnstock' THEN 'vnstock_data'
                ELSE source
            END
        WHERE valid_to IS NULL
          AND (namespace = 'vnstock' OR source = 'vnstock')
    """)
