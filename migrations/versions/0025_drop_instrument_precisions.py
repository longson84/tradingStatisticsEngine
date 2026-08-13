"""Drop unused provider display-precision fields from instruments.

Revision ID: 0025
Revises: 0024
Create Date: 2026-08-13
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("instruments", "quote_precision")
    op.drop_column("instruments", "base_precision")


def downgrade() -> None:
    # These provider display hints were never canonical execution constraints.
    # A downgrade restores nullable compatibility columns; a later catalog sync
    # would be required to repopulate their former values.
    op.add_column("instruments", sa.Column("base_precision", sa.Integer()))
    op.add_column("instruments", sa.Column("quote_precision", sa.Integer()))
