"""Remove legacy market and free-text exchange instrument columns.

Revision ID: 0019
Revises: 0018
Create Date: 2026-08-12
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM instruments AS instrument
                LEFT JOIN venues AS venue ON venue.id = instrument.venue_id
                WHERE instrument.instrument_type = 'common_stock'
                  AND (venue.country_code IS NULL
                       OR venue.country_code NOT IN ('US', 'VN'))
            ) THEN
                RAISE EXCEPTION
                    'Cannot remove market: every equity needs a US or VN venue';
            END IF;
            IF EXISTS (
                SELECT ticker
                FROM instruments
                WHERE venue_id IS NULL
                GROUP BY ticker
                HAVING count(*) > 1
            ) THEN
                RAISE EXCEPTION
                    'Cannot remove market: duplicate venue-less tickers exist';
            END IF;
        END $$
    """)

    op.drop_index(
        "uq_instrument_symbols_current_identity",
        table_name="instrument_symbols",
    )
    op.drop_constraint(
        "ck_instrument_symbols_market", "instrument_symbols", type_="check"
    )
    op.drop_column("instrument_symbols", "market")
    op.create_index(
        "ix_instrument_symbols_current_lookup",
        "instrument_symbols",
        ["namespace", "symbol"],
        unique=False,
        postgresql_where=sa.text("valid_to IS NULL"),
    )

    op.drop_constraint("uq_instruments_id_market", "instruments", type_="unique")
    op.drop_index(
        "uq_instruments_market_ticker_without_venue", table_name="instruments"
    )
    op.drop_constraint("ck_instruments_market", "instruments", type_="check")
    op.drop_column("instruments", "exchange")
    op.drop_column("instruments", "market")
    op.create_index(
        "uq_instruments_ticker_without_venue",
        "instruments",
        ["ticker"],
        unique=True,
        postgresql_where=sa.text("venue_id IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_instruments_ticker_without_venue", table_name="instruments")
    op.add_column(
        "instruments", sa.Column("market", sa.String(length=16), nullable=True)
    )
    op.add_column(
        "instruments", sa.Column("exchange", sa.String(length=32), nullable=True)
    )
    op.execute("""
        UPDATE instruments AS instrument
        SET market = CASE
                WHEN instrument.instrument_type IN ('spot', 'reference_rate')
                    THEN 'CRYPTO'
                ELSE venue.country_code
            END,
            exchange = venue.code
        FROM venues AS venue
        WHERE venue.id = instrument.venue_id
    """)
    op.execute("""
        UPDATE instruments
        SET market = 'CRYPTO'
        WHERE instrument_type = 'reference_rate'
    """)
    op.alter_column("instruments", "market", nullable=False)
    op.create_check_constraint(
        "ck_instruments_market",
        "instruments",
        "market IN ('US', 'VN', 'CRYPTO')",
    )
    op.create_unique_constraint(
        "uq_instruments_id_market", "instruments", ["id", "market"]
    )
    op.create_index(
        "uq_instruments_market_ticker_without_venue",
        "instruments",
        ["market", "ticker"],
        unique=True,
        postgresql_where=sa.text("venue_id IS NULL"),
    )

    op.drop_index(
        "ix_instrument_symbols_current_lookup", table_name="instrument_symbols"
    )
    op.add_column(
        "instrument_symbols",
        sa.Column("market", sa.String(length=16), nullable=True),
    )
    op.execute("""
        UPDATE instrument_symbols AS symbol
        SET market = instrument.market
        FROM instruments AS instrument
        WHERE instrument.id = symbol.instrument_id
    """)
    op.alter_column("instrument_symbols", "market", nullable=False)
    op.create_check_constraint(
        "ck_instrument_symbols_market",
        "instrument_symbols",
        "market IN ('US', 'VN', 'CRYPTO')",
    )
    op.create_index(
        "uq_instrument_symbols_current_identity",
        "instrument_symbols",
        ["namespace", "market", "symbol"],
        unique=True,
        postgresql_where=sa.text("valid_to IS NULL"),
    )
