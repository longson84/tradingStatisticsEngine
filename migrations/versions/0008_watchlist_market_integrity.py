"""Enforce watchlist membership market integrity in PostgreSQL.

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-04
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
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
    op.create_unique_constraint(
        "uq_instruments_id_market", "instruments", ["id", "market"]
    )
    op.create_unique_constraint(
        "uq_watchlists_id_market", "watchlists", ["id", "market"]
    )
    op.drop_constraint(
        "watchlist_memberships_watchlist_id_fkey",
        "watchlist_memberships",
        type_="foreignkey",
    )
    op.drop_constraint(
        "watchlist_memberships_instrument_id_fkey",
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


def downgrade() -> None:
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
        "watchlist_memberships_instrument_id_fkey",
        "watchlist_memberships",
        "instruments",
        ["instrument_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "watchlist_memberships_watchlist_id_fkey",
        "watchlist_memberships",
        "watchlists",
        ["watchlist_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_constraint("uq_watchlists_id_market", "watchlists", type_="unique")
    op.drop_constraint("uq_instruments_id_market", "instruments", type_="unique")
    op.drop_column("watchlist_memberships", "market")
