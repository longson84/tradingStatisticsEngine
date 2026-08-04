"""Create canonical daily price bars.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-03
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "price_bars",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("instrument_id", sa.BigInteger(), nullable=False),
        sa.Column("trading_date", sa.Date(), nullable=False),
        sa.Column("open", sa.Float(), nullable=False),
        sa.Column("high", sa.Float(), nullable=False),
        sa.Column("low", sa.Float(), nullable=False),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("volume", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("price_scale", sa.Integer(), nullable=False),
        sa.Column("price_basis", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.CheckConstraint("open > 0", name="ck_price_bars_open_positive"),
        sa.CheckConstraint("high > 0", name="ck_price_bars_high_positive"),
        sa.CheckConstraint("low > 0", name="ck_price_bars_low_positive"),
        sa.CheckConstraint("close > 0", name="ck_price_bars_close_positive"),
        sa.CheckConstraint("high >= low", name="ck_price_bars_high_gte_low"),
        sa.CheckConstraint(
            "volume IS NULL OR volume >= 0", name="ck_price_bars_volume"
        ),
        sa.CheckConstraint("price_scale > 0", name="ck_price_bars_price_scale"),
        sa.ForeignKeyConstraint(
            ["instrument_id"], ["instruments.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "instrument_id",
            "trading_date",
            "price_basis",
            name="uq_price_bars_instrument_date_basis",
        ),
    )
    op.create_index(
        "ix_price_bars_trading_date", "price_bars", ["trading_date"]
    )


def downgrade() -> None:
    op.drop_index("ix_price_bars_trading_date", table_name="price_bars")
    op.drop_table("price_bars")
