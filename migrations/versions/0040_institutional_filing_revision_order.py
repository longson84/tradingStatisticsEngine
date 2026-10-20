"""Add deterministic SEC 13F amendment ordering.

Revision ID: 0040
Revises: 0039
Create Date: 2026-10-20
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0040"
down_revision: str | None = "0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "institutional_filings",
        sa.Column("amendment_number", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "institutional_filings",
        sa.Column("is_complete", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "institutional_filing_positions",
        sa.Column(
            "mapping_status", sa.String(16), nullable=False,
            server_default="unmapped",
        ),
    )
    op.create_check_constraint(
        "ck_institutional_positions_mapping_status",
        "institutional_filing_positions",
        "mapping_status IN ('mapped', 'unmapped', 'ambiguous')",
    )
    op.execute(
        "UPDATE institutional_filing_positions "
        "SET mapping_status = 'mapped' WHERE instrument_id IS NOT NULL"
    )
    op.execute(
        "UPDATE institutional_filing_positions AS p SET reported_value_unit = 'USD' "
        "FROM institutional_filings AS f "
        "WHERE p.filing_id = f.id AND f.filed_at >= DATE '2023-01-03'"
    )
    op.alter_column(
        "institutional_filing_positions", "reported_value_unit",
        server_default="USD",
    )
    op.create_table(
        "institutional_position_rejections",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("filing_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.ForeignKey("institutional_filings.id", ondelete="CASCADE"), nullable=True),
        sa.Column("accession_number", sa.String(32), nullable=True),
        sa.Column("source_row_number", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("filing_id", "source_row_number", name="uq_institutional_rejection_source_row"),
    )


def downgrade() -> None:
    op.alter_column(
        "institutional_filing_positions", "reported_value_unit",
        server_default="USD_thousands",
    )
    op.drop_table("institutional_position_rejections")
    op.drop_constraint(
        "ck_institutional_positions_mapping_status",
        "institutional_filing_positions",
        type_="check",
    )
    op.drop_column("institutional_filing_positions", "mapping_status")
    op.drop_column("institutional_filings", "is_complete")
    op.drop_column("institutional_filings", "amendment_number")
