"""Make instrument_symbols authoritative and drop instruments.ticker.

Revision ID: 0024
Revises: 0023
Create Date: 2026-08-13
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Older catalog writers created provider symbols but did not always create
    # the canonical namespace. Preserve the exact compatibility value before
    # removing it; the current-primary uniqueness index rejects ambiguity.
    op.execute("""
        INSERT INTO instrument_symbols (
            instrument_id, namespace, symbol, is_primary, source
        )
        SELECT instrument.id, 'canonical', instrument.ticker, true, instrument.source
        FROM instruments AS instrument
        WHERE NOT EXISTS (
            SELECT 1
            FROM instrument_symbols AS symbol
            WHERE symbol.instrument_id = instrument.id
              AND symbol.namespace = 'canonical'
              AND symbol.valid_to IS NULL
              AND symbol.is_primary
        )
    """)
    op.drop_index("uq_instruments_venue_ticker", table_name="instruments")
    op.drop_index("uq_instruments_ticker_without_venue", table_name="instruments")
    op.drop_column("instruments", "ticker")


def downgrade() -> None:
    op.add_column(
        "instruments",
        sa.Column("ticker", sa.String(length=64), nullable=True),
    )
    op.execute("""
        UPDATE instruments AS instrument
        SET ticker = symbol.symbol
        FROM instrument_symbols AS symbol
        WHERE symbol.instrument_id = instrument.id
          AND symbol.namespace = 'canonical'
          AND symbol.valid_to IS NULL
          AND symbol.is_primary
    """)
    op.alter_column("instruments", "ticker", nullable=False)
    op.create_index(
        "uq_instruments_ticker_without_venue",
        "instruments",
        ["ticker"],
        unique=True,
        postgresql_where=sa.text("venue_id IS NULL"),
    )
    op.create_index(
        "uq_instruments_venue_ticker",
        "instruments",
        ["venue_id", "ticker"],
        unique=True,
        postgresql_where=sa.text("venue_id IS NOT NULL"),
    )
