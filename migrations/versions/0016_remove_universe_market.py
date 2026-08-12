"""Remove the overloaded market classification from universes.

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-10
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_universes_market", "universes", type_="check")
    op.drop_column("universes", "market")


def downgrade() -> None:
    # The former schema can represent only non-empty, single-market universes.
    # Refuse to invent a classification for an empty or mixed universe.
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT universe.id
                FROM universes AS universe
                LEFT JOIN universe_memberships AS membership
                  ON membership.universe_id = universe.id
                LEFT JOIN instruments AS instrument
                  ON instrument.id = membership.instrument_id
                GROUP BY universe.id
                HAVING count(DISTINCT instrument.market) != 1
            ) THEN
                RAISE EXCEPTION
                    'Cannot downgrade: a universe is empty or contains multiple instrument markets';
            END IF;
        END $$
    """)
    op.add_column(
        "universes", sa.Column("market", sa.String(length=16), nullable=True)
    )
    op.execute("""
        UPDATE universes AS universe
        SET market = derived.market
        FROM (
            SELECT membership.universe_id, min(instrument.market) AS market
            FROM universe_memberships AS membership
            JOIN instruments AS instrument
              ON instrument.id = membership.instrument_id
            GROUP BY membership.universe_id
        ) AS derived
        WHERE derived.universe_id = universe.id
    """)
    op.alter_column("universes", "market", nullable=False)
    op.create_check_constraint(
        "ck_universes_market",
        "universes",
        "market IN ('US', 'VN', 'CRYPTO')",
    )
