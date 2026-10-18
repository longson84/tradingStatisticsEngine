"""Add canonical daily Instrument trade statistics.

Revision ID: 0037
Revises: 0036
Create Date: 2026-10-18
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0037"
down_revision: str | None = "0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Freeze this migration's schema independently of future provider contracts.
_NUMERIC_COLUMNS = (
    "market_cap", "total_shares", "matched_volume", "matched_value",
    "deal_volume", "deal_value", "total_volume", "total_value",
    "total_buy_trade", "total_buy_trade_volume", "total_sell_trade",
    "total_sell_trade_volume", "total_net_trade_volume",
    "total_buy_unmatched_volume", "total_sell_unmatched_volume",
    "average_buy_trade_volume", "average_sell_trade_volume",
)


def upgrade() -> None:
    op.create_table(
        "instrument_daily_trade_statistics",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
                  autoincrement=True, nullable=False),
        sa.Column("instrument_id", sa.BigInteger(), nullable=False),
        sa.Column("trading_date", sa.Date(), nullable=False),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        *(sa.Column(
            name,
            sa.Numeric(38, 18 if name in {
                "average_buy_trade_volume", "average_sell_trade_volume",
            } else 6),
            nullable=False,
        ) for name in _NUMERIC_COLUMNS),
        sa.CheckConstraint(
            "schema_version > 0", name="ck_daily_trade_statistics_schema_version",
        ),
        *(
            sa.CheckConstraint(
                f"CAST({name} AS NUMERIC) >= 0",
                name=f"ck_daily_trade_statistics_{name}",
            )
            for name in _NUMERIC_COLUMNS if name != "total_net_trade_volume"
        ),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "instrument_id", "trading_date",
            name="uq_instrument_daily_trade_statistics_identity",
        ),
    )


def downgrade() -> None:
    op.drop_table("instrument_daily_trade_statistics")
