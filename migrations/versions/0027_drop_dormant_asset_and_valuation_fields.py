"""Drop dormant asset contract identity and valuation timestamp fields.

Revision ID: 0027
Revises: 0026
Create Date: 2026-08-14
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("provider_valuation_observations", "observed_at")
    op.drop_index("uq_assets_network_contract", table_name="assets")
    op.drop_column("assets", "contract_address")
    op.drop_column("assets", "network")


def downgrade() -> None:
    op.add_column(
        "assets",
        sa.Column("network", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "assets",
        sa.Column("contract_address", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "uq_assets_network_contract",
        "assets",
        ["network", "contract_address"],
        unique=True,
        postgresql_where=sa.text("contract_address IS NOT NULL"),
    )
    op.add_column(
        "provider_valuation_observations",
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
    )
