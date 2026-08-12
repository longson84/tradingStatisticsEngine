"""Add the ETH/USD reference-rate instrument.

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-10
"""
from typing import Sequence

from alembic import op


revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO assets (
            canonical_code, name, asset_type, is_active, source
        ) VALUES ('ETH', 'Ethereum', 'crypto', true, 'system')
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
            'CRYPTO', 'ETH-USD', 'reference_rate', 'USD', true,
            'yahoo_finance'
        FROM assets AS base
        CROSS JOIN assets AS quote
        WHERE base.canonical_code = 'ETH'
          AND quote.canonical_code = 'USD'
          AND NOT EXISTS (
              SELECT 1 FROM instruments
              WHERE market = 'CRYPTO'
                AND ticker = 'ETH-USD'
                AND venue_id IS NULL
          )
    """)
    op.execute("""
        INSERT INTO instrument_symbols (
            instrument_id, namespace, market, symbol, is_primary, source
        )
        SELECT
            instrument.id, 'yahoo_finance', 'CRYPTO', 'ETH-USD', true,
            'yahoo_finance'
        FROM instruments AS instrument
        WHERE instrument.market = 'CRYPTO'
          AND instrument.ticker = 'ETH-USD'
          AND instrument.venue_id IS NULL
          AND NOT EXISTS (
              SELECT 1 FROM instrument_symbols AS symbol
              WHERE symbol.namespace = 'yahoo_finance'
                AND symbol.market = 'CRYPTO'
                AND symbol.symbol = 'ETH-USD'
                AND symbol.valid_to IS NULL
          )
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM instruments
        WHERE market = 'CRYPTO'
          AND ticker = 'ETH-USD'
          AND venue_id IS NULL
          AND instrument_type = 'reference_rate'
    """)
