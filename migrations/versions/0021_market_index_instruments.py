"""Add canonical market-index instruments for relative-strength benchmarks.

Revision ID: 0021
Revises: 0020
Create Date: 2026-08-13
"""
from typing import Sequence

from alembic import op


revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_instruments_market_index_identity",
        "instruments",
        "instrument_type != 'market_index' OR "
        "(company_id IS NULL AND venue_id IS NULL "
        "AND base_asset_id IS NULL AND quote_asset_id IS NULL "
        "AND settlement_asset_id IS NULL)",
    )
    op.execute("""
        INSERT INTO instruments (
            company_id, venue_id, base_asset_id, quote_asset_id,
            settlement_asset_id, ticker, instrument_type, currency,
            is_active, source
        )
        SELECT
            NULL, NULL, NULL, NULL, NULL, definition.ticker,
            'market_index', definition.currency, true, 'system'
        FROM (VALUES
            ('SPX', 'USD'),
            ('VN30', 'VND')
        ) AS definition(ticker, currency)
        WHERE NOT EXISTS (
            SELECT 1
            FROM instruments AS existing
            WHERE existing.ticker = definition.ticker
              AND existing.venue_id IS NULL
        )
    """)
    op.execute("""
        INSERT INTO instrument_symbols (
            instrument_id, namespace, symbol, is_primary, source
        )
        SELECT
            instrument.id, definition.namespace, definition.provider_symbol,
            true, definition.source
        FROM (VALUES
            ('SPX', 'yfinance', '^GSPC', 'yahoo_finance'),
            ('VN30', 'vnstock_data', 'VN30', 'vnstock_data')
        ) AS definition(ticker, namespace, provider_symbol, source)
        JOIN instruments AS instrument
          ON instrument.ticker = definition.ticker
         AND instrument.venue_id IS NULL
         AND instrument.instrument_type = 'market_index'
        WHERE NOT EXISTS (
            SELECT 1
            FROM instrument_symbols AS existing
            WHERE existing.instrument_id = instrument.id
              AND existing.namespace = definition.namespace
              AND existing.valid_to IS NULL
              AND existing.is_primary
        )
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM instruments
        WHERE instrument_type = 'market_index'
          AND venue_id IS NULL
          AND ticker IN ('SPX', 'VN30')
    """)
    op.drop_constraint(
        "ck_instruments_market_index_identity",
        "instruments",
        type_="check",
    )
