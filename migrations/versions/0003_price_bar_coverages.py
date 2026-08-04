"""Add per-instrument price-bar coverage summaries.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-03
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "price_bar_coverages",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("instrument_id", sa.BigInteger(), nullable=False),
        sa.Column("price_basis", sa.String(length=32), nullable=False),
        sa.Column("first_date", sa.Date(), nullable=False),
        sa.Column("last_date", sa.Date(), nullable=False),
        sa.Column("row_count", sa.BigInteger(), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("row_count > 0", name="ck_price_bar_coverage_rows"),
        sa.ForeignKeyConstraint(
            ["instrument_id"], ["instruments.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "instrument_id", "price_basis", name="uq_price_bar_coverage_basis"
        ),
    )
    op.create_index(
        "ix_price_bar_coverages_instrument_id",
        "price_bar_coverages",
        ["instrument_id"],
    )
    op.execute("""
        INSERT INTO price_bar_coverages (
            instrument_id, price_basis, first_date, last_date,
            row_count, source, fetched_at
        )
        SELECT instrument_id, price_basis, MIN(trading_date), MAX(trading_date),
               COUNT(*), MIN(source), MAX(fetched_at)
        FROM price_bars
        GROUP BY instrument_id, price_basis
    """)


def downgrade() -> None:
    op.drop_index(
        "ix_price_bar_coverages_instrument_id",
        table_name="price_bar_coverages",
    )
    op.drop_table("price_bar_coverages")
