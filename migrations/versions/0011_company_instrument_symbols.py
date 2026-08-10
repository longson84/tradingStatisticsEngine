"""Separate issuer identity, instruments, and symbol mappings.

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-09
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("legal_name", sa.String(length=255), nullable=True),
        sa.Column("country_code", sa.String(length=2), nullable=False),
        sa.Column("sector", sa.String(length=255), nullable=True),
        sa.Column("industry", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("country_code IN ('US', 'VN')", name="ck_companies_country"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "company_identifiers",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.BigInteger(), nullable=False),
        sa.Column("namespace", sa.String(length=64), nullable=False),
        sa.Column("value", sa.String(length=255), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("namespace", "value", name="uq_company_identifier"),
    )
    op.create_index(
        op.f("ix_company_identifiers_company_id"),
        "company_identifiers",
        ["company_id"],
    )

    op.add_column("instruments", sa.Column("company_id", sa.BigInteger(), nullable=True))
    op.add_column(
        "instruments",
        sa.Column("instrument_type", sa.String(length=32), nullable=True),
    )
    op.add_column("instruments", sa.Column("share_class", sa.String(length=64)))
    op.add_column("instruments", sa.Column("currency", sa.String(length=3), nullable=True))

    # One issuer per legacy instrument is the only lossless backfill. Later
    # imports may reconcile share classes through stable identifiers such as CIK.
    op.execute("""
        INSERT INTO companies (
            id, display_name, legal_name, country_code, sector, industry,
            is_active, source, created_at, updated_at
        )
        SELECT
            id, company_name, company_name, market, sector, industry,
            is_active, source, created_at, updated_at
        FROM instruments
    """)
    op.execute("UPDATE instruments SET company_id = id")
    op.execute("UPDATE instruments SET instrument_type = 'common_stock'")
    op.execute("UPDATE instruments SET currency = CASE market WHEN 'VN' THEN 'VND' ELSE 'USD' END")
    op.execute("""
        SELECT setval(
            pg_get_serial_sequence('companies', 'id'),
            COALESCE((SELECT MAX(id) FROM companies), 1),
            EXISTS (SELECT 1 FROM companies)
        )
    """)

    op.alter_column("instruments", "company_id", nullable=False)
    op.alter_column("instruments", "instrument_type", nullable=False)
    op.alter_column("instruments", "currency", nullable=False)
    op.create_foreign_key(
        "fk_instruments_company_id_companies",
        "instruments",
        "companies",
        ["company_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(op.f("ix_instruments_company_id"), "instruments", ["company_id"])

    op.create_table(
        "instrument_symbols",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("instrument_id", sa.BigInteger(), nullable=False),
        sa.Column("namespace", sa.String(length=64), nullable=False),
        sa.Column("market", sa.String(length=2), nullable=False),
        sa.Column("symbol", sa.String(length=64), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("market IN ('US', 'VN')", name="ck_instrument_symbols_market"),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from",
            name="ck_instrument_symbols_validity",
        ),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_instrument_symbols_instrument_id"),
        "instrument_symbols",
        ["instrument_id"],
    )
    op.create_index(
        "uq_instrument_symbols_current_identity",
        "instrument_symbols",
        ["namespace", "market", "symbol"],
        unique=True,
        postgresql_where=sa.text("valid_to IS NULL"),
    )
    op.create_index(
        "uq_instrument_symbols_current_primary",
        "instrument_symbols",
        ["instrument_id", "namespace"],
        unique=True,
        postgresql_where=sa.text("valid_to IS NULL AND is_primary"),
    )
    op.execute("""
        INSERT INTO instrument_symbols (
            instrument_id, namespace, market, symbol, is_primary, source
        )
        SELECT id, 'canonical', market, ticker, true, source
        FROM instruments
    """)

    op.drop_column("instruments", "industry")
    op.drop_column("instruments", "sector")
    op.drop_column("instruments", "company_name")


def downgrade() -> None:
    op.add_column("instruments", sa.Column("company_name", sa.String(length=255)))
    op.add_column("instruments", sa.Column("sector", sa.String(length=255)))
    op.add_column("instruments", sa.Column("industry", sa.String(length=255)))
    op.execute("""
        UPDATE instruments AS instrument
        SET company_name = company.display_name,
            sector = company.sector,
            industry = company.industry
        FROM companies AS company
        WHERE company.id = instrument.company_id
    """)
    op.alter_column("instruments", "company_name", nullable=False)

    op.drop_index("uq_instrument_symbols_current_primary", table_name="instrument_symbols")
    op.drop_index("uq_instrument_symbols_current_identity", table_name="instrument_symbols")
    op.drop_index(op.f("ix_instrument_symbols_instrument_id"), table_name="instrument_symbols")
    op.drop_table("instrument_symbols")
    op.drop_index(op.f("ix_instruments_company_id"), table_name="instruments")
    op.drop_constraint(
        "fk_instruments_company_id_companies", "instruments", type_="foreignkey"
    )
    op.drop_column("instruments", "currency")
    op.drop_column("instruments", "share_class")
    op.drop_column("instruments", "instrument_type")
    op.drop_column("instruments", "company_id")
    op.drop_index(op.f("ix_company_identifiers_company_id"), table_name="company_identifiers")
    op.drop_table("company_identifiers")
    op.drop_table("companies")
