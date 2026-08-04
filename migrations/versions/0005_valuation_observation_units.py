"""Allow sparse valuation timestamps and preserve valuation units.

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-03
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "provider_valuation_observations",
        "observed_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
    )
    op.add_column(
        "provider_valuation_observations",
        sa.Column("unit", sa.String(length=16), nullable=False),
    )
    op.add_column(
        "provider_valuation_observations",
        sa.Column("currency", sa.String(length=3), nullable=True),
    )
    op.add_column(
        "provider_valuation_observations",
        sa.Column("scale", sa.BigInteger(), nullable=False),
    )
    op.create_check_constraint(
        "ck_provider_valuation_unit",
        "provider_valuation_observations",
        "unit IN ('currency', 'ratio', 'percent')",
    )
    op.create_check_constraint(
        "ck_provider_valuation_scale",
        "provider_valuation_observations",
        "scale > 0",
    )
    op.create_check_constraint(
        "ck_provider_valuation_currency",
        "provider_valuation_observations",
        "currency IS NULL OR length(currency) = 3",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_provider_valuation_currency",
        "provider_valuation_observations",
        type_="check",
    )
    op.drop_constraint(
        "ck_provider_valuation_scale",
        "provider_valuation_observations",
        type_="check",
    )
    op.drop_constraint(
        "ck_provider_valuation_unit",
        "provider_valuation_observations",
        type_="check",
    )
    op.drop_column("provider_valuation_observations", "scale")
    op.drop_column("provider_valuation_observations", "currency")
    op.drop_column("provider_valuation_observations", "unit")
    op.alter_column(
        "provider_valuation_observations",
        "observed_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )
