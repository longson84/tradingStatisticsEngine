"""Normalize fundamental snapshot and calculation identities.

Revision ID: 0023
Revises: 0022
Create Date: 2026-08-13
"""
from typing import Sequence

from alembic import op


revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        UPDATE fundamental_facts AS fact
        SET calculation_version =
            'provider:' ||
            left(
                trim(both '-' from regexp_replace(
                    lower(report.source), '[^a-z0-9]+', '-', 'g'
                )),
                32
            ) || ':' ||
            left(md5(trim(split_part(
                coalesce(report.methodology, ''), '; acquired via ', 1
            ))), 12)
        FROM fundamental_reports AS report
        WHERE report.id = fact.report_id
          AND fact.calculation_version LIKE 'legacy-%'
    """)
    op.execute("""
        UPDATE fundamental_reports
        SET report_key = 'snapshot:' || substring(report_key from 8)
        WHERE report_key LIKE 'legacy:%'
    """)
    op.execute("""
        UPDATE provider_valuation_observations
        SET observation_key = 'snapshot:' || substring(observation_key from 8)
        WHERE observation_key LIKE 'legacy:%'
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE fundamental_facts AS fact
        SET calculation_version = 'legacy-' || report.source
        FROM fundamental_reports AS report
        WHERE report.id = fact.report_id
          AND fact.calculation_version LIKE 'provider:%'
          AND report.report_key LIKE 'snapshot:%'
    """)
    op.execute("""
        UPDATE fundamental_reports
        SET report_key = 'legacy:' || substring(report_key from 10)
        WHERE report_key LIKE 'snapshot:%'
    """)
    op.execute("""
        UPDATE provider_valuation_observations
        SET observation_key = 'legacy:' || substring(observation_key from 10)
        WHERE observation_key LIKE 'snapshot:%'
    """)
