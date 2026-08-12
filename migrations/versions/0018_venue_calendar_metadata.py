"""Add canonical venue calendar, timezone, and session cutoff metadata.

Revision ID: 0018
Revises: 0017
Create Date: 2026-08-11
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "venues", sa.Column("timezone_name", sa.String(length=64), nullable=True)
    )
    op.add_column(
        "venues",
        sa.Column("trading_calendar_code", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "venues", sa.Column("session_cutoff_time", sa.Time(), nullable=True)
    )
    op.execute("""
        UPDATE venues
        SET timezone_name = CASE
                WHEN code IN (
                    'NASDAQ', 'NYSE', 'NYSE_AMERICAN', 'NYSE_ARCA',
                    'CBOE_BZX', 'IEX'
                ) THEN 'America/New_York'
                WHEN code IN ('HOSE', 'HNX', 'UPCOM') THEN 'Asia/Ho_Chi_Minh'
                WHEN code = 'BINANCE_SPOT' THEN 'UTC'
            END,
            trading_calendar_code = CASE
                WHEN code IN (
                    'NASDAQ', 'NYSE', 'NYSE_AMERICAN', 'NYSE_ARCA',
                    'CBOE_BZX', 'IEX'
                ) THEN 'US_EQUITIES'
                WHEN code IN ('HOSE', 'HNX', 'UPCOM') THEN 'VN_EQUITIES'
                WHEN code = 'BINANCE_SPOT' THEN 'CRYPTO_24_7'
            END,
            session_cutoff_time = CASE
                WHEN code IN (
                    'NASDAQ', 'NYSE', 'NYSE_AMERICAN', 'NYSE_ARCA',
                    'CBOE_BZX', 'IEX'
                ) THEN TIME '16:15:00'
                WHEN code IN ('HOSE', 'HNX', 'UPCOM') THEN TIME '15:15:00'
                WHEN code = 'BINANCE_SPOT' THEN TIME '00:00:00'
            END,
            updated_at = now()
    """)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM venues
                WHERE timezone_name IS NULL
                   OR trading_calendar_code IS NULL
                   OR session_cutoff_time IS NULL
            ) THEN
                RAISE EXCEPTION
                    'Every venue must have timezone and trading calendar metadata';
            END IF;
        END $$
    """)
    op.alter_column("venues", "timezone_name", nullable=False)
    op.alter_column("venues", "trading_calendar_code", nullable=False)
    op.alter_column("venues", "session_cutoff_time", nullable=False)


def downgrade() -> None:
    op.drop_column("venues", "session_cutoff_time")
    op.drop_column("venues", "trading_calendar_code")
    op.drop_column("venues", "timezone_name")
