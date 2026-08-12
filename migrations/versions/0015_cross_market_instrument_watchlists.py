"""Make watchlists ordered cross-market instrument collections.

Revision ID: 0015
Revises: 0014
Create Date: 2026-08-10
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Names were previously unique only within a market. Preserve both lists if
    # the same name exists in US and VN before establishing global uniqueness.
    op.execute("""
        UPDATE watchlists AS watchlist
        SET name = watchlist.name || ' (' || watchlist.market || ')',
            name_key = watchlist.name_key || ' (' || lower(watchlist.market) || ')'
        WHERE watchlist.name_key IN (
            SELECT name_key
            FROM watchlists
            GROUP BY name_key
            HAVING count(*) > 1
        )
    """)

    op.drop_constraint(
        "fk_watchlist_memberships_instrument_market",
        "watchlist_memberships",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_watchlist_memberships_watchlist_market",
        "watchlist_memberships",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_watchlist_memberships_instrument",
        "watchlist_memberships",
        "instruments",
        ["instrument_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_watchlist_memberships_watchlist",
        "watchlist_memberships",
        "watchlists",
        ["watchlist_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_column("watchlist_memberships", "market")

    op.drop_constraint("uq_watchlists_id_market", "watchlists", type_="unique")
    op.drop_constraint(
        "uq_watchlists_market_name_key", "watchlists", type_="unique"
    )
    op.drop_constraint("ck_watchlists_market", "watchlists", type_="check")
    op.drop_column("watchlists", "market")
    op.create_unique_constraint(
        "uq_watchlists_name_key", "watchlists", ["name_key"]
    )


def downgrade() -> None:
    # The former schema cannot represent mixed-market membership. Refuse a
    # lossy downgrade rather than silently dropping members.
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT membership.watchlist_id
                FROM watchlist_memberships AS membership
                JOIN instruments AS instrument
                  ON instrument.id = membership.instrument_id
                GROUP BY membership.watchlist_id
                HAVING count(DISTINCT instrument.market) > 1
                    OR min(instrument.market) NOT IN ('US', 'VN')
            ) THEN
                RAISE EXCEPTION
                    'Cannot downgrade: a watchlist is mixed-market or non-equity-market';
            END IF;
        END $$
    """)

    op.drop_constraint("uq_watchlists_name_key", "watchlists", type_="unique")
    op.add_column(
        "watchlists", sa.Column("market", sa.String(length=2), nullable=True)
    )
    op.execute("""
        UPDATE watchlists AS watchlist
        SET market = COALESCE(
            (
                SELECT min(instrument.market)
                FROM watchlist_memberships AS membership
                JOIN instruments AS instrument
                  ON instrument.id = membership.instrument_id
                WHERE membership.watchlist_id = watchlist.id
            ),
            'US'
        )
    """)
    op.alter_column("watchlists", "market", nullable=False)
    op.create_check_constraint(
        "ck_watchlists_market", "watchlists", "market IN ('US', 'VN')"
    )
    op.create_unique_constraint(
        "uq_watchlists_market_name_key", "watchlists", ["market", "name_key"]
    )
    op.create_unique_constraint(
        "uq_watchlists_id_market", "watchlists", ["id", "market"]
    )

    op.add_column(
        "watchlist_memberships",
        sa.Column("market", sa.String(length=2), nullable=True),
    )
    op.execute("""
        UPDATE watchlist_memberships AS membership
        SET market = watchlist.market
        FROM watchlists AS watchlist
        WHERE watchlist.id = membership.watchlist_id
    """)
    op.alter_column("watchlist_memberships", "market", nullable=False)
    op.drop_constraint(
        "fk_watchlist_memberships_instrument",
        "watchlist_memberships",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_watchlist_memberships_watchlist",
        "watchlist_memberships",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_watchlist_memberships_watchlist_market",
        "watchlist_memberships",
        "watchlists",
        ["watchlist_id", "market"],
        ["id", "market"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_watchlist_memberships_instrument_market",
        "watchlist_memberships",
        "instruments",
        ["instrument_id", "market"],
        ["id", "market"],
        ondelete="CASCADE",
    )
