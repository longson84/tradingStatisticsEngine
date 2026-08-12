"""Replace legacy equity venues with canonical venue identities.

Revision ID: 0017
Revises: 0016
Create Date: 2026-08-11
"""
from typing import Sequence

from alembic import op


revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO venues (
            code, name, venue_type, country_code, is_active, source
        ) VALUES
            ('NASDAQ', 'Nasdaq Stock Market', 'exchange', 'US', true,
             'system:equity-venue-registry'),
            ('NYSE', 'New York Stock Exchange', 'exchange', 'US', true,
             'system:equity-venue-registry'),
            ('NYSE_AMERICAN', 'NYSE American', 'exchange', 'US', true,
             'system:equity-venue-registry'),
            ('NYSE_ARCA', 'NYSE Arca', 'exchange', 'US', true,
             'system:equity-venue-registry'),
            ('CBOE_BZX', 'Cboe BZX Exchange', 'exchange', 'US', true,
             'system:equity-venue-registry'),
            ('IEX', 'Investors Exchange', 'exchange', 'US', true,
             'system:equity-venue-registry'),
            ('HOSE', 'Ho Chi Minh Stock Exchange', 'exchange', 'VN', true,
             'system:equity-venue-registry'),
            ('HNX', 'Hanoi Stock Exchange', 'exchange', 'VN', true,
             'system:equity-venue-registry'),
            ('UPCOM', 'Unlisted Public Company Market', 'market', 'VN', true,
             'system:equity-venue-registry')
        ON CONFLICT (code) DO UPDATE SET
            name = EXCLUDED.name,
            venue_type = EXCLUDED.venue_type,
            country_code = EXCLUDED.country_code,
            is_active = true,
            source = EXCLUDED.source,
            updated_at = now()
    """)
    op.execute("""
        WITH exchange_mapping(country_code, exchange_key, venue_code) AS (
            VALUES
                ('US', 'NASDAQ', 'NASDAQ'),
                ('US', 'NASDAQ STOCK MARKET', 'NASDAQ'),
                ('US', 'NYSE', 'NYSE'),
                ('US', 'NEW YORK STOCK EXCHANGE', 'NYSE'),
                ('US', 'NYSE AMERICAN', 'NYSE_AMERICAN'),
                ('US', 'NYSE MKT', 'NYSE_AMERICAN'),
                ('US', 'AMEX', 'NYSE_AMERICAN'),
                ('US', 'NYSE ARCA', 'NYSE_ARCA'),
                ('US', 'ARCA', 'NYSE_ARCA'),
                ('US', 'BATS', 'CBOE_BZX'),
                ('US', 'BATS GLOBAL MARKETS', 'CBOE_BZX'),
                ('US', 'CBOE BZX', 'CBOE_BZX'),
                ('US', 'CBOE BZX EXCHANGE', 'CBOE_BZX'),
                ('US', 'IEX', 'IEX'),
                ('US', 'IEXG', 'IEX'),
                ('US', 'INVESTORS EXCHANGE', 'IEX'),
                ('VN', 'HOSE', 'HOSE'),
                ('VN', 'HSX', 'HOSE'),
                ('VN', 'HO CHI MINH STOCK EXCHANGE', 'HOSE'),
                ('VN', 'HNX', 'HNX'),
                ('VN', 'HANOI STOCK EXCHANGE', 'HNX'),
                ('VN', 'UPCOM', 'UPCOM'),
                ('VN', 'UPCOM MARKET', 'UPCOM')
        )
        UPDATE instruments AS instrument
        SET venue_id = venue.id,
            exchange = venue.code,
            updated_at = now()
        FROM exchange_mapping AS mapping
        JOIN venues AS venue ON venue.code = mapping.venue_code
        WHERE instrument.company_id IS NOT NULL
          AND instrument.market = mapping.country_code
          AND upper(regexp_replace(
              trim(instrument.exchange), '[[:space:]]+', ' ', 'g'
          )) =
              mapping.exchange_key
    """)
    op.execute("""
        DELETE FROM venues AS venue
        WHERE venue.code LIKE 'LEGACY:%'
          AND NOT EXISTS (
              SELECT 1 FROM instruments AS instrument
              WHERE instrument.venue_id = venue.id
          )
    """)


def downgrade() -> None:
    op.execute("""
        INSERT INTO venues (
            code, name, venue_type, country_code, is_active, source
        )
        SELECT DISTINCT
            'LEGACY:' || instrument.market || ':' || upper(trim(instrument.exchange)),
            instrument.exchange,
            'exchange',
            instrument.market,
            true,
            'company_import'
        FROM instruments AS instrument
        WHERE instrument.company_id IS NOT NULL
          AND instrument.exchange IS NOT NULL
          AND trim(instrument.exchange) <> ''
        ON CONFLICT (code) DO NOTHING
    """)
    op.execute("""
        UPDATE instruments AS instrument
        SET venue_id = venue.id,
            updated_at = now()
        FROM venues AS venue
        WHERE instrument.company_id IS NOT NULL
          AND instrument.exchange IS NOT NULL
          AND venue.code =
              'LEGACY:' || instrument.market || ':' || upper(trim(instrument.exchange))
    """)
    op.execute("""
        DELETE FROM venues AS venue
        WHERE venue.code IN (
            'NASDAQ', 'NYSE', 'NYSE_AMERICAN', 'NYSE_ARCA', 'CBOE_BZX', 'IEX',
            'HOSE', 'HNX', 'UPCOM'
        )
          AND NOT EXISTS (
              SELECT 1 FROM instruments AS instrument
              WHERE instrument.venue_id = venue.id
          )
    """)
