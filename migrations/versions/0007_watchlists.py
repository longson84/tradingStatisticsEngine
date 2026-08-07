"""Create single-market watchlists and memberships.

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-04
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "watchlists",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("name_key", sa.String(length=100), nullable=False),
        sa.Column("market", sa.String(length=2), nullable=False),
        sa.Column(
            "description", sa.String(length=500), server_default="", nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("market IN ('US', 'VN')", name="ck_watchlists_market"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "market", "name_key", name="uq_watchlists_market_name_key"
        ),
    )
    op.create_table(
        "watchlist_memberships",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("watchlist_id", sa.BigInteger(), nullable=False),
        sa.Column("instrument_id", sa.BigInteger(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "position >= 0", name="ck_watchlist_memberships_position"
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"], ["instruments.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["watchlist_id"], ["watchlists.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "watchlist_id", "instrument_id", name="uq_watchlist_membership"
        ),
    )
    op.create_index(
        op.f("ix_watchlist_memberships_instrument_id"),
        "watchlist_memberships",
        ["instrument_id"],
    )
    op.create_index(
        op.f("ix_watchlist_memberships_watchlist_id"),
        "watchlist_memberships",
        ["watchlist_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_watchlist_memberships_watchlist_id"),
        table_name="watchlist_memberships",
    )
    op.drop_index(
        op.f("ix_watchlist_memberships_instrument_id"),
        table_name="watchlist_memberships",
    )
    op.drop_table("watchlist_memberships")
    op.drop_table("watchlists")
