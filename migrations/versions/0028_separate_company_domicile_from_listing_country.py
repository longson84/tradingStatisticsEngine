"""Separate Company domicile from Instrument listing country.

Revision ID: 0028
Revises: 0027
Create Date: 2026-08-14
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_companies_country", "companies", type_="check")
    op.alter_column(
        "companies",
        "country_code",
        new_column_name="domicile_country_code",
        existing_type=sa.String(length=2),
        existing_nullable=False,
        nullable=True,
    )
    # The retired values came from Universe/listing scope, not verified issuer
    # domicile. Venue.country_code preserves that listing geography.
    op.execute("UPDATE companies SET domicile_country_code = NULL")
    op.create_check_constraint(
        "ck_companies_domicile_country",
        "companies",
        "domicile_country_code IS NULL OR "
        "(length(domicile_country_code) = 2 "
        "AND substr(domicile_country_code, 1, 1) BETWEEN 'A' AND 'Z' "
        "AND substr(domicile_country_code, 2, 1) BETWEEN 'A' AND 'Z')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_companies_domicile_country",
        "companies",
        type_="check",
    )
    op.execute(
        """
        UPDATE companies AS company
        SET domicile_country_code = listing.country_code
        FROM (
            SELECT instrument.company_id, min(venue.country_code) AS country_code
            FROM instruments AS instrument
            JOIN venues AS venue ON venue.id = instrument.venue_id
            WHERE instrument.company_id IS NOT NULL
              AND venue.country_code IN ('US', 'VN')
            GROUP BY instrument.company_id
            HAVING count(DISTINCT venue.country_code) = 1
        ) AS listing
        WHERE company.id = listing.company_id
          AND company.domicile_country_code IS NULL
        """
    )
    # The legacy schema requires a value even for orphan Companies whose
    # listing scope cannot be reconstructed. Those rows were US static-list
    # residue at cutover; use the old default only for structural rollback.
    op.execute(
        """
        UPDATE companies
        SET domicile_country_code = 'US'
        WHERE domicile_country_code IS NULL
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM companies
                WHERE domicile_country_code NOT IN ('US', 'VN')
            ) THEN
                RAISE EXCEPTION
                    'Cannot restore the legacy US/VN Company country contract';
            END IF;
        END $$
        """
    )
    op.alter_column(
        "companies",
        "domicile_country_code",
        new_column_name="country_code",
        existing_type=sa.String(length=2),
        existing_nullable=True,
        nullable=False,
    )
    op.create_check_constraint(
        "ck_companies_country",
        "companies",
        "country_code IN ('US', 'VN')",
    )
