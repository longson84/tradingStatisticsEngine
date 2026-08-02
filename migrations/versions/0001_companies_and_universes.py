"""Create instruments and current universe memberships.

Revision ID: 0001
Revises:
Create Date: 2026-08-02
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "instruments",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("market", sa.String(length=2), nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("sector", sa.String(length=255), nullable=True),
        sa.Column("industry", sa.String(length=255), nullable=True),
        sa.Column("exchange", sa.String(length=32), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
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
        sa.CheckConstraint("market IN ('US', 'VN')", name="ck_instruments_market"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("market", "ticker", name="uq_instruments_market_ticker"),
    )
    op.create_table(
        "universes",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("market", sa.String(length=2), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=False),
        sa.Column("as_of", sa.String(length=64), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.String(length=100), nullable=False),
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
        sa.CheckConstraint("market IN ('US', 'VN')", name="ck_universes_market"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "universe_memberships",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("universe_id", sa.BigInteger(), nullable=False),
        sa.Column("instrument_id", sa.BigInteger(), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["universe_id"], ["universes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "universe_id", "instrument_id", name="uq_universe_membership"
        ),
    )
    op.create_index(
        op.f("ix_universe_memberships_instrument_id"),
        "universe_memberships",
        ["instrument_id"],
    )
    op.create_index(
        op.f("ix_universe_memberships_universe_id"),
        "universe_memberships",
        ["universe_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_universe_memberships_universe_id"),
        table_name="universe_memberships",
    )
    op.drop_index(
        op.f("ix_universe_memberships_instrument_id"),
        table_name="universe_memberships",
    )
    op.drop_table("universe_memberships")
    op.drop_table("universes")
    op.drop_table("instruments")
