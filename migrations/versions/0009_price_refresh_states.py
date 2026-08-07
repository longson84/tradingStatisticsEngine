"""Track provider checks separately from observable price bars.

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-07
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "price_refresh_states",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("instrument_id", sa.BigInteger(), nullable=False),
        sa.Column("price_basis", sa.String(length=32), nullable=False),
        sa.Column("attempted_through", sa.Date(), nullable=False),
        sa.Column("returned_through", sa.Date(), nullable=True),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("primary_source", sa.String(length=100), nullable=False),
        sa.Column("selected_source", sa.String(length=100), nullable=True),
        sa.Column("detail", sa.String(length=1000), nullable=True),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "outcome IN ('current', 'checked_no_new_bar', 'failed')",
            name="ck_price_refresh_states_outcome",
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"], ["instruments.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "instrument_id", "price_basis", name="uq_price_refresh_state_basis"
        ),
    )
    op.create_index(
        "ix_price_refresh_states_instrument_id",
        "price_refresh_states",
        ["instrument_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_price_refresh_states_instrument_id",
        table_name="price_refresh_states",
    )
    op.drop_table("price_refresh_states")
