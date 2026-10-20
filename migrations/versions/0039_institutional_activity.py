"""Add canonical SEC 13F institutional activity storage.

Revision ID: 0039
Revises: 0038
Create Date: 2026-10-20
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0039"
down_revision: str | None = "0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "instrument_identifiers",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("instrument_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("namespace", sa.String(32), nullable=False),
        sa.Column("value", sa.String(64), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("namespace IN ('cusip', 'figi', 'share_class_figi')", name="ck_instrument_identifiers_namespace"),
        sa.CheckConstraint("valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from", name="ck_instrument_identifiers_validity"),
        sa.UniqueConstraint("instrument_id", "namespace", "value", "valid_from", name="uq_instrument_identifier_identity"),
    )
    op.create_index("ix_instrument_identifiers_lookup", "instrument_identifiers", ["namespace", "value", "valid_from", "valid_to"])

    op.create_table(
        "institutional_managers",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("sec_cik", sa.String(10), nullable=False, unique=True),
        sa.Column("legal_name", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("is_curated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("length(sec_cik) BETWEEN 1 AND 10", name="ck_institutional_managers_cik"),
    )

    op.create_table(
        "institutional_filings",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("manager_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.ForeignKey("institutional_managers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("accession_number", sa.String(32), nullable=False, unique=True),
        sa.Column("form_type", sa.String(16), nullable=False),
        sa.Column("report_period", sa.Date(), nullable=False),
        sa.Column("filed_at", sa.Date(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("amendment_type", sa.String(32), nullable=True),
        sa.Column("source_url", sa.String(1000), nullable=False),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("form_type IN ('13F-HR', '13F-HR/A')", name="ck_institutional_filings_form"),
        sa.CheckConstraint("amendment_type IS NULL OR amendment_type IN ('restatement', 'new_holdings')", name="ck_institutional_filings_amendment"),
    )
    op.create_index("ix_institutional_filings_period", "institutional_filings", ["manager_id", "report_period", "accepted_at"])

    op.create_table(
        "institutional_filing_positions",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("filing_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.ForeignKey("institutional_filings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_row_number", sa.Integer(), nullable=False),
        sa.Column("instrument_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.ForeignKey("instruments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("raw_cusip", sa.String(16), nullable=False),
        sa.Column("issuer_name", sa.String(255), nullable=False),
        sa.Column("title_of_class", sa.String(100), nullable=False),
        sa.Column("reported_value", sa.Numeric(38, 6), nullable=False),
        sa.Column("reported_value_unit", sa.String(16), nullable=False, server_default="USD"),
        sa.Column("shares", sa.Numeric(38, 6), nullable=False),
        sa.Column("share_type", sa.String(8), nullable=False),
        sa.Column("put_call", sa.String(8), nullable=True),
        sa.Column("investment_discretion", sa.String(32), nullable=True),
        sa.Column("voting_sole", sa.Numeric(38, 6), nullable=False),
        sa.Column("voting_shared", sa.Numeric(38, 6), nullable=False),
        sa.Column("voting_none", sa.Numeric(38, 6), nullable=False),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("source_row_number > 0", name="ck_institutional_positions_row"),
        sa.CheckConstraint("reported_value >= 0", name="ck_institutional_positions_value"),
        sa.CheckConstraint("shares > 0", name="ck_institutional_positions_shares"),
        sa.CheckConstraint("share_type IN ('SH', 'PRN')", name="ck_institutional_positions_share_type"),
        sa.CheckConstraint("put_call IS NULL OR put_call IN ('PUT', 'CALL')", name="ck_institutional_positions_put_call"),
        sa.CheckConstraint("voting_sole >= 0 AND voting_shared >= 0 AND voting_none >= 0", name="ck_institutional_positions_voting"),
        sa.UniqueConstraint("filing_id", "source_row_number", name="uq_institutional_position_source_row"),
    )
    op.create_index("ix_institutional_positions_instrument", "institutional_filing_positions", ["instrument_id", "filing_id"])
    op.create_index("ix_institutional_positions_cusip", "institutional_filing_positions", ["raw_cusip"])


def downgrade() -> None:
    op.drop_table("institutional_filing_positions")
    op.drop_table("institutional_filings")
    op.drop_table("institutional_managers")
    op.drop_table("instrument_identifiers")
