"""Add venue-less reference-rate instruments.

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-10
"""
from typing import Sequence

from alembic import op


revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_instruments_reference_rate_identity",
        "instruments",
        "instrument_type != 'reference_rate' OR "
        "(company_id IS NULL AND venue_id IS NULL "
        "AND base_asset_id IS NOT NULL AND quote_asset_id IS NOT NULL)",
    )
    op.execute("""
        INSERT INTO assets (
            canonical_code, name, asset_type, is_active, source
        ) VALUES
            ('BTC', 'Bitcoin', 'crypto', true, 'system'),
            ('USD', 'United States Dollar', 'fiat', true, 'system')
        ON CONFLICT (canonical_code) DO NOTHING
    """)
    op.execute("""
        INSERT INTO instruments (
            company_id, venue_id, base_asset_id, quote_asset_id,
            settlement_asset_id, market, ticker, instrument_type,
            currency, is_active, source
        )
        SELECT
            NULL, NULL, base.id, quote.id, quote.id,
            'CRYPTO', 'BTC-USD', 'reference_rate', 'USD', true,
            'yahoo_finance'
        FROM assets AS base
        CROSS JOIN assets AS quote
        WHERE base.canonical_code = 'BTC'
          AND quote.canonical_code = 'USD'
          AND NOT EXISTS (
              SELECT 1 FROM instruments
              WHERE market = 'CRYPTO'
                AND ticker = 'BTC-USD'
                AND venue_id IS NULL
          )
    """)
    op.execute("""
        INSERT INTO instrument_symbols (
            instrument_id, namespace, market, symbol, is_primary, source
        )
        SELECT
            instrument.id, 'yahoo_finance', 'CRYPTO', 'BTC-USD', true,
            'yahoo_finance'
        FROM instruments AS instrument
        WHERE instrument.market = 'CRYPTO'
          AND instrument.ticker = 'BTC-USD'
          AND instrument.venue_id IS NULL
          AND NOT EXISTS (
              SELECT 1 FROM instrument_symbols AS symbol
              WHERE symbol.namespace = 'yahoo_finance'
                AND symbol.market = 'CRYPTO'
                AND symbol.symbol = 'BTC-USD'
                AND symbol.valid_to IS NULL
          )
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM instruments
        WHERE market = 'CRYPTO'
          AND ticker = 'BTC-USD'
          AND venue_id IS NULL
          AND instrument_type = 'reference_rate'
    """)
    op.drop_constraint(
        "ck_instruments_reference_rate_identity",
        "instruments",
        type_="check",
    )
