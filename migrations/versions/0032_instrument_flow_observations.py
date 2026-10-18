"""Add canonical Instrument participant-flow observations.

Revision ID: 0032
Revises: 0031
Create Date: 2026-10-18
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0032"
down_revision: str | None = "0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "instrument_flow_observations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("instrument_id", sa.BigInteger(), nullable=False),
        sa.Column("trading_date", sa.Date(), nullable=False),
        sa.Column("participant_type", sa.String(length=16), nullable=False),
        sa.Column("buy_volume", sa.Numeric(38, 6), nullable=False),
        sa.Column("buy_value", sa.Numeric(38, 6), nullable=False),
        sa.Column("sell_volume", sa.Numeric(38, 6), nullable=False),
        sa.Column("sell_value", sa.Numeric(38, 6), nullable=False),
        sa.Column("net_volume", sa.Numeric(38, 6), nullable=False),
        sa.Column("net_value", sa.Numeric(38, 6), nullable=False),
        sa.Column("currency", sa.String(length=16), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "participant_type IN ('foreign', 'proprietary')",
            name="ck_instrument_flow_observations_participant",
        ),
        sa.CheckConstraint(
            "buy_volume >= 0", name="ck_instrument_flow_observations_buy_volume"
        ),
        sa.CheckConstraint(
            "buy_value >= 0", name="ck_instrument_flow_observations_buy_value"
        ),
        sa.CheckConstraint(
            "sell_volume >= 0", name="ck_instrument_flow_observations_sell_volume"
        ),
        sa.CheckConstraint(
            "sell_value >= 0", name="ck_instrument_flow_observations_sell_value"
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"], ["instruments.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "instrument_id",
            "trading_date",
            "participant_type",
            name="uq_instrument_flow_observation_identity",
        ),
    )
    op.create_index(
        "ix_instrument_flow_observations_instrument_id",
        "instrument_flow_observations",
        ["instrument_id"],
    )
    op.create_index(
        "ix_instrument_flow_observations_trading_date",
        "instrument_flow_observations",
        ["trading_date"],
    )
    op.create_table(
        "instrument_flow_coverages",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("instrument_id", sa.BigInteger(), nullable=False),
        sa.Column("participant_type", sa.String(length=16), nullable=False),
        sa.Column("first_date", sa.Date(), nullable=False),
        sa.Column("last_date", sa.Date(), nullable=False),
        sa.Column("row_count", sa.BigInteger(), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "participant_type IN ('foreign', 'proprietary')",
            name="ck_instrument_flow_coverages_participant",
        ),
        sa.CheckConstraint(
            "row_count > 0", name="ck_instrument_flow_coverages_rows"
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"], ["instruments.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "instrument_id",
            "participant_type",
            name="uq_instrument_flow_coverage_participant",
        ),
    )
    op.create_index(
        "ix_instrument_flow_coverages_instrument_id",
        "instrument_flow_coverages",
        ["instrument_id"],
    )
    _replace_dataset_checks(include_foreign_flow=True)


def downgrade() -> None:
    _replace_dataset_checks(include_foreign_flow=False)
    op.drop_index(
        "ix_instrument_flow_coverages_instrument_id",
        table_name="instrument_flow_coverages",
    )
    op.drop_table("instrument_flow_coverages")
    op.drop_index(
        "ix_instrument_flow_observations_trading_date",
        table_name="instrument_flow_observations",
    )
    op.drop_index(
        "ix_instrument_flow_observations_instrument_id",
        table_name="instrument_flow_observations",
    )
    op.drop_table("instrument_flow_observations")


def _replace_dataset_checks(*, include_foreign_flow: bool) -> None:
    values = "'prices', 'fundamentals'"
    if include_foreign_flow:
        values += ", 'foreign_flow'"
    for name, table in (
        ("ck_data_operation_runs_dataset", "data_operation_runs"),
        ("ck_data_operation_batch_steps_dataset", "data_operation_batch_steps"),
    ):
        op.drop_constraint(name, table, type_="check")
        op.create_check_constraint(name, table, f"dataset IN ({values})")
