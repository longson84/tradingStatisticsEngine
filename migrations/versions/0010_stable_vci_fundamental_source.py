"""Use stable VCI source identity for VN fundamental upserts.

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-08
"""
from typing import Sequence

from alembic import op


revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Calculation identity must move with report source identity; otherwise the
    # next provider refresh would append a second fact version to each report.
    op.execute("""
        UPDATE fundamental_facts AS fact
        SET calculation_version = 'legacy-vci'
        FROM fundamental_reports AS report
        JOIN instruments AS instrument ON instrument.id = report.instrument_id
        WHERE fact.report_id = report.id
          AND instrument.market = 'VN'
          AND report.source LIKE 'vnstock-vci-%'
          AND fact.calculation_version LIKE 'legacy-vnstock-vci-%'
    """)
    op.execute("""
        UPDATE fundamental_reports AS report
        SET source = 'vci'
        FROM instruments AS instrument
        WHERE instrument.id = report.instrument_id
          AND instrument.market = 'VN'
          AND report.source LIKE 'vnstock-vci-%'
    """)
    op.execute("""
        UPDATE provider_valuation_observations AS observation
        SET source = 'vci'
        FROM instruments AS instrument
        WHERE instrument.id = observation.instrument_id
          AND instrument.market = 'VN'
          AND observation.source LIKE 'vnstock-vci-%'
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE fundamental_facts AS fact
        SET calculation_version = 'legacy-vnstock-vci-4.0.5'
        FROM fundamental_reports AS report
        JOIN instruments AS instrument ON instrument.id = report.instrument_id
        WHERE fact.report_id = report.id
          AND instrument.market = 'VN'
          AND report.source = 'vci'
          AND fact.calculation_version = 'legacy-vci'
    """)
    op.execute("""
        UPDATE fundamental_reports AS report
        SET source = 'vnstock-vci-4.0.5'
        FROM instruments AS instrument
        WHERE instrument.id = report.instrument_id
          AND instrument.market = 'VN'
          AND report.source = 'vci'
    """)
    op.execute("""
        UPDATE provider_valuation_observations AS observation
        SET source = 'vnstock-vci-4.0.5'
        FROM instruments AS instrument
        WHERE instrument.id = observation.instrument_id
          AND instrument.market = 'VN'
          AND observation.source = 'vci'
    """)
