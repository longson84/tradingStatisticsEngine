"""Create point-in-time fundamental data model.

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-03
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fundamental_reports",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("instrument_id", sa.BigInteger(), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("report_key", sa.String(length=255), nullable=False),
        sa.Column("provider_report_id", sa.String(length=255), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column("fiscal_year", sa.Integer(), nullable=True),
        sa.Column("fiscal_quarter", sa.Integer(), nullable=True),
        sa.Column("period_type", sa.String(length=16), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_session_date", sa.Date(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reporting_currency", sa.String(length=3), nullable=True),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("is_restatement", sa.Boolean(), nullable=False),
        sa.Column("raw_payload_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "period_type IN ('quarterly', 'annual', 'earnings', 'other')",
            name="ck_fundamental_reports_period_type",
        ),
        sa.CheckConstraint(
            "scope IN ('consolidated', 'standalone', 'unknown')",
            name="ck_fundamental_reports_scope",
        ),
        sa.CheckConstraint(
            "fiscal_quarter IS NULL OR fiscal_quarter BETWEEN 1 AND 4",
            name="ck_fundamental_reports_quarter",
        ),
        sa.CheckConstraint(
            "reporting_currency IS NULL OR length(reporting_currency) = 3",
            name="ck_fundamental_reports_currency",
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"], ["instruments.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "instrument_id",
            "source",
            "report_key",
            name="uq_fundamental_report_source_key",
        ),
    )
    op.create_index(
        "ix_fundamental_reports_instrument_effective",
        "fundamental_reports",
        ["instrument_id", "effective_session_date"],
    )
    op.create_index(
        "ix_fundamental_reports_instrument_period",
        "fundamental_reports",
        ["instrument_id", "period_end"],
    )

    op.create_table(
        "fundamental_facts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("report_id", sa.BigInteger(), nullable=False),
        sa.Column("metric_code", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Numeric(precision=38, scale=10), nullable=False),
        sa.Column("unit", sa.String(length=16), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("scale", sa.BigInteger(), nullable=False),
        sa.Column("period_basis", sa.String(length=16), nullable=False),
        sa.Column("fact_kind", sa.String(length=24), nullable=False),
        sa.Column("source_field", sa.String(length=255), nullable=True),
        sa.Column("calculation_version", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "unit IN ('currency', 'shares', 'per_share', 'ratio', 'percent', 'count')",
            name="ck_fundamental_facts_unit",
        ),
        sa.CheckConstraint(
            "period_basis IN ('instant', 'quarter', 'ytd', 'annual', 'ttm')",
            name="ck_fundamental_facts_period_basis",
        ),
        sa.CheckConstraint(
            "fact_kind IN ('reported', 'provider_derived', 'system_derived')",
            name="ck_fundamental_facts_kind",
        ),
        sa.CheckConstraint("scale > 0", name="ck_fundamental_facts_scale"),
        sa.CheckConstraint(
            "currency IS NULL OR length(currency) = 3",
            name="ck_fundamental_facts_currency",
        ),
        sa.ForeignKeyConstraint(
            ["report_id"], ["fundamental_reports.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "report_id",
            "metric_code",
            "period_basis",
            "fact_kind",
            "calculation_version",
            name="uq_fundamental_fact_identity",
        ),
    )
    op.create_index(
        "ix_fundamental_facts_report_id",
        "fundamental_facts",
        ["report_id"],
    )
    op.create_index(
        "ix_fundamental_facts_metric",
        "fundamental_facts",
        ["metric_code"],
    )

    op.create_table(
        "provider_valuation_observations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("instrument_id", sa.BigInteger(), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("observation_key", sa.String(length=255), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_session_date", sa.Date(), nullable=False),
        sa.Column("metric_code", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Numeric(precision=38, scale=10), nullable=False),
        sa.Column("methodology", sa.String(length=1000), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"], ["instruments.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "instrument_id",
            "source",
            "observation_key",
            "metric_code",
            name="uq_provider_valuation_observation",
        ),
    )
    op.create_index(
        "ix_provider_valuation_instrument_effective",
        "provider_valuation_observations",
        ["instrument_id", "effective_session_date"],
    )

    op.create_table(
        "fundamental_refresh_runs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.String(length=64), nullable=False),
        sa.Column("universe_id", sa.BigInteger(), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("provider_version", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("requested_count", sa.Integer(), nullable=False),
        sa.Column("reused_count", sa.Integer(), nullable=False),
        sa.Column("succeeded_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_summary", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('running', 'completed', 'failed')",
            name="ck_fundamental_refresh_runs_status",
        ),
        sa.CheckConstraint(
            "requested_count >= 0 AND reused_count >= 0 AND "
            "succeeded_count >= 0 AND failed_count >= 0",
            name="ck_fundamental_refresh_runs_counts",
        ),
        sa.ForeignKeyConstraint(
            ["universe_id"], ["universes.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id"),
    )
    op.create_index(
        "ix_fundamental_refresh_runs_universe_started",
        "fundamental_refresh_runs",
        ["universe_id", "started_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_fundamental_refresh_runs_universe_started",
        table_name="fundamental_refresh_runs",
    )
    op.drop_table("fundamental_refresh_runs")
    op.drop_index(
        "ix_provider_valuation_instrument_effective",
        table_name="provider_valuation_observations",
    )
    op.drop_table("provider_valuation_observations")
    op.drop_index("ix_fundamental_facts_metric", table_name="fundamental_facts")
    op.drop_index("ix_fundamental_facts_report_id", table_name="fundamental_facts")
    op.drop_table("fundamental_facts")
    op.drop_index(
        "ix_fundamental_reports_instrument_period",
        table_name="fundamental_reports",
    )
    op.drop_index(
        "ix_fundamental_reports_instrument_effective",
        table_name="fundamental_reports",
    )
    op.drop_table("fundamental_reports")
