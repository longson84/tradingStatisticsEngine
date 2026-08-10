"""Add canonical assets, venues, and crypto spot instruments.

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-09
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("canonical_code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("asset_type", sa.String(length=32), nullable=False),
        sa.Column("network", sa.String(length=64), nullable=True),
        sa.Column("contract_address", sa.String(length=255), nullable=True),
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
        sa.CheckConstraint(
            "asset_type IN ('equity', 'crypto', 'fiat', 'stablecoin')",
            name="ck_assets_type",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("canonical_code"),
    )
    op.create_index(
        "uq_assets_network_contract",
        "assets",
        ["network", "contract_address"],
        unique=True,
        postgresql_where=sa.text("contract_address IS NOT NULL"),
    )

    op.create_table(
        "venues",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("venue_type", sa.String(length=32), nullable=False),
        sa.Column("country_code", sa.String(length=2), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )

    op.create_table(
        "asset_issuers",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("asset_id", sa.BigInteger(), nullable=False),
        sa.Column("company_id", sa.BigInteger(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from",
            name="ck_asset_issuers_validity",
        ),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "asset_id",
            "company_id",
            "role",
            "valid_from",
            name="uq_asset_issuers_identity",
        ),
    )
    op.create_index(
        op.f("ix_asset_issuers_asset_id"), "asset_issuers", ["asset_id"]
    )
    op.create_index(
        op.f("ix_asset_issuers_company_id"), "asset_issuers", ["company_id"]
    )
    op.create_index(
        "uq_asset_issuers_current",
        "asset_issuers",
        ["asset_id", "company_id", "role"],
        unique=True,
        postgresql_where=sa.text("valid_to IS NULL"),
    )

    op.add_column("instruments", sa.Column("venue_id", sa.BigInteger()))
    op.add_column("instruments", sa.Column("base_asset_id", sa.BigInteger()))
    op.add_column("instruments", sa.Column("quote_asset_id", sa.BigInteger()))
    op.add_column("instruments", sa.Column("settlement_asset_id", sa.BigInteger()))
    op.add_column("instruments", sa.Column("base_precision", sa.Integer()))
    op.add_column("instruments", sa.Column("quote_precision", sa.Integer()))
    op.add_column(
        "instruments", sa.Column("price_tick_size", sa.Numeric(38, 18))
    )
    op.add_column(
        "instruments", sa.Column("quantity_step_size", sa.Numeric(38, 18))
    )
    op.add_column(
        "instruments", sa.Column("minimum_quantity", sa.Numeric(38, 18))
    )
    op.add_column(
        "instruments", sa.Column("minimum_notional", sa.Numeric(38, 18))
    )
    op.create_foreign_key(
        "fk_instruments_venue_id_venues",
        "instruments",
        "venues",
        ["venue_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_instruments_base_asset_id_assets",
        "instruments",
        "assets",
        ["base_asset_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_instruments_quote_asset_id_assets",
        "instruments",
        "assets",
        ["quote_asset_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_instruments_settlement_asset_id_assets",
        "instruments",
        "assets",
        ["settlement_asset_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(op.f("ix_instruments_venue_id"), "instruments", ["venue_id"])
    op.create_index(
        op.f("ix_instruments_base_asset_id"), "instruments", ["base_asset_id"]
    )
    op.create_index(
        op.f("ix_instruments_quote_asset_id"), "instruments", ["quote_asset_id"]
    )
    op.create_index(
        op.f("ix_instruments_settlement_asset_id"),
        "instruments",
        ["settlement_asset_id"],
    )

    # Backfill the existing equity instruments into the generalized asset model.
    op.execute("""
        INSERT INTO assets (
            canonical_code, name, asset_type, is_active, source
        )
        SELECT
            'EQUITY:' || instrument.market || ':' || instrument.id,
            company.display_name ||
                CASE WHEN instrument.share_class IS NULL THEN ''
                     ELSE ' ' || instrument.share_class END,
            'equity', instrument.is_active, instrument.source
        FROM instruments AS instrument
        JOIN companies AS company ON company.id = instrument.company_id
    """)
    op.execute("""
        INSERT INTO assets (
            canonical_code, name, asset_type, is_active, source
        ) VALUES
            ('USD', 'United States Dollar', 'fiat', true, 'system'),
            ('VND', 'Vietnamese Dong', 'fiat', true, 'system')
    """)
    op.execute("""
        INSERT INTO venues (
            code, name, venue_type, country_code, is_active, source
        )
        SELECT DISTINCT
            'LEGACY:' || market || ':' || upper(trim(exchange)),
            exchange,
            'exchange',
            market,
            true,
            'company_import'
        FROM instruments
        WHERE exchange IS NOT NULL AND trim(exchange) <> ''
    """)
    op.execute("""
        INSERT INTO venues (
            code, name, venue_type, country_code, is_active, source
        ) VALUES (
            'BINANCE_SPOT', 'Binance Spot', 'exchange', NULL, true, 'system'
        )
    """)
    op.execute("""
        UPDATE instruments AS instrument
        SET base_asset_id = asset.id
        FROM assets AS asset
        WHERE asset.canonical_code =
            'EQUITY:' || instrument.market || ':' || instrument.id
    """)
    op.execute("""
        UPDATE instruments AS instrument
        SET quote_asset_id = asset.id,
            settlement_asset_id = asset.id
        FROM assets AS asset
        WHERE asset.canonical_code = instrument.currency
    """)
    op.execute("""
        UPDATE instruments AS instrument
        SET venue_id = venue.id
        FROM venues AS venue
        WHERE venue.code =
            'LEGACY:' || instrument.market || ':' || upper(trim(instrument.exchange))
    """)
    op.execute("""
        INSERT INTO asset_issuers (
            asset_id, company_id, role, source
        )
        SELECT base_asset_id, company_id, 'issuer', source
        FROM instruments
        WHERE base_asset_id IS NOT NULL AND company_id IS NOT NULL
    """)

    op.drop_constraint("uq_instruments_market_ticker", "instruments", type_="unique")
    op.drop_constraint("ck_instruments_market", "instruments", type_="check")
    op.alter_column(
        "instruments", "market", type_=sa.String(length=16), existing_nullable=False
    )
    op.alter_column(
        "instruments", "ticker", type_=sa.String(length=64), existing_nullable=False
    )
    op.alter_column(
        "instruments", "currency", type_=sa.String(length=16), existing_nullable=False
    )
    op.alter_column("instruments", "company_id", nullable=True)
    op.create_check_constraint(
        "ck_instruments_market",
        "instruments",
        "market IN ('US', 'VN', 'CRYPTO')",
    )
    op.create_check_constraint(
        "ck_instruments_spot_identity",
        "instruments",
        "instrument_type != 'spot' OR "
        "(company_id IS NULL AND venue_id IS NOT NULL "
        "AND base_asset_id IS NOT NULL AND quote_asset_id IS NOT NULL)",
    )
    op.create_index(
        "uq_instruments_market_ticker_without_venue",
        "instruments",
        ["market", "ticker"],
        unique=True,
        postgresql_where=sa.text("venue_id IS NULL"),
    )
    op.create_index(
        "uq_instruments_venue_ticker",
        "instruments",
        ["venue_id", "ticker"],
        unique=True,
        postgresql_where=sa.text("venue_id IS NOT NULL"),
    )

    op.drop_constraint(
        "ck_instrument_symbols_market", "instrument_symbols", type_="check"
    )
    op.alter_column(
        "instrument_symbols",
        "market",
        type_=sa.String(length=16),
        existing_nullable=False,
    )
    op.create_check_constraint(
        "ck_instrument_symbols_market",
        "instrument_symbols",
        "market IN ('US', 'VN', 'CRYPTO')",
    )

    op.drop_constraint("ck_universes_market", "universes", type_="check")
    op.alter_column(
        "universes", "market", type_=sa.String(length=16), existing_nullable=False
    )
    op.create_check_constraint(
        "ck_universes_market",
        "universes",
        "market IN ('US', 'VN', 'CRYPTO')",
    )
    op.alter_column(
        "price_bars", "currency", type_=sa.String(length=16), existing_nullable=False
    )


def downgrade() -> None:
    # Crypto instruments cannot satisfy the legacy mandatory-company model.
    op.execute("DELETE FROM instruments WHERE market = 'CRYPTO'")

    op.alter_column(
        "price_bars", "currency", type_=sa.String(length=3), existing_nullable=False
    )
    op.drop_constraint("ck_universes_market", "universes", type_="check")
    op.alter_column(
        "universes", "market", type_=sa.String(length=2), existing_nullable=False
    )
    op.create_check_constraint(
        "ck_universes_market", "universes", "market IN ('US', 'VN')"
    )
    op.drop_constraint(
        "ck_instrument_symbols_market", "instrument_symbols", type_="check"
    )
    op.alter_column(
        "instrument_symbols",
        "market",
        type_=sa.String(length=2),
        existing_nullable=False,
    )
    op.create_check_constraint(
        "ck_instrument_symbols_market",
        "instrument_symbols",
        "market IN ('US', 'VN')",
    )

    op.drop_index("uq_instruments_venue_ticker", table_name="instruments")
    op.drop_index(
        "uq_instruments_market_ticker_without_venue", table_name="instruments"
    )
    op.drop_constraint("ck_instruments_spot_identity", "instruments", type_="check")
    op.drop_constraint("ck_instruments_market", "instruments", type_="check")
    op.alter_column("instruments", "company_id", nullable=False)
    op.alter_column(
        "instruments", "currency", type_=sa.String(length=3), existing_nullable=False
    )
    op.alter_column(
        "instruments", "ticker", type_=sa.String(length=32), existing_nullable=False
    )
    op.alter_column(
        "instruments", "market", type_=sa.String(length=2), existing_nullable=False
    )
    op.create_check_constraint(
        "ck_instruments_market", "instruments", "market IN ('US', 'VN')"
    )
    op.create_unique_constraint(
        "uq_instruments_market_ticker", "instruments", ["market", "ticker"]
    )

    op.drop_index(op.f("ix_instruments_settlement_asset_id"), table_name="instruments")
    op.drop_index(op.f("ix_instruments_quote_asset_id"), table_name="instruments")
    op.drop_index(op.f("ix_instruments_base_asset_id"), table_name="instruments")
    op.drop_index(op.f("ix_instruments_venue_id"), table_name="instruments")
    op.drop_constraint(
        "fk_instruments_settlement_asset_id_assets", "instruments", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_instruments_quote_asset_id_assets", "instruments", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_instruments_base_asset_id_assets", "instruments", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_instruments_venue_id_venues", "instruments", type_="foreignkey"
    )
    op.drop_column("instruments", "settlement_asset_id")
    op.drop_column("instruments", "quote_asset_id")
    op.drop_column("instruments", "base_asset_id")
    op.drop_column("instruments", "venue_id")
    op.drop_column("instruments", "minimum_notional")
    op.drop_column("instruments", "minimum_quantity")
    op.drop_column("instruments", "quantity_step_size")
    op.drop_column("instruments", "price_tick_size")
    op.drop_column("instruments", "quote_precision")
    op.drop_column("instruments", "base_precision")

    op.drop_index("uq_asset_issuers_current", table_name="asset_issuers")
    op.drop_index(op.f("ix_asset_issuers_company_id"), table_name="asset_issuers")
    op.drop_index(op.f("ix_asset_issuers_asset_id"), table_name="asset_issuers")
    op.drop_table("asset_issuers")
    op.drop_table("venues")
    op.drop_index("uq_assets_network_contract", table_name="assets")
    op.drop_table("assets")
