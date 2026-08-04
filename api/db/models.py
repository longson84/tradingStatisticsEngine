"""Canonical application persistence models."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


_ID_TYPE = BigInteger().with_variant(Integer, "sqlite")


class Instrument(Base):
    """One tradable security shown as a company in the current UI."""

    __tablename__ = "instruments"
    __table_args__ = (
        CheckConstraint("market IN ('US', 'VN')", name="ck_instruments_market"),
        UniqueConstraint("market", "ticker", name="uq_instruments_market_ticker"),
    )

    id: Mapped[int] = mapped_column(_ID_TYPE, primary_key=True, autoincrement=True)
    market: Mapped[str] = mapped_column(String(2), nullable=False)
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sector: Mapped[str | None] = mapped_column(String(255))
    industry: Mapped[str | None] = mapped_column(String(255))
    exchange: Mapped[str | None] = mapped_column(String(32))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    memberships: Mapped[list[UniverseMembership]] = relationship(
        back_populates="instrument", cascade="all, delete-orphan"
    )
    price_bars: Mapped[list[PriceBar]] = relationship(
        back_populates="instrument", cascade="all, delete-orphan"
    )
    price_bar_coverages: Mapped[list[PriceBarCoverage]] = relationship(
        back_populates="instrument", cascade="all, delete-orphan"
    )
    fundamental_reports: Mapped[list[FundamentalReport]] = relationship(
        back_populates="instrument", cascade="all, delete-orphan"
    )
    provider_valuation_observations: Mapped[list[ProviderValuationObservation]] = relationship(
        back_populates="instrument", cascade="all, delete-orphan"
    )


class Universe(Base):
    """A named current constituent universe such as US500 or VN30."""

    __tablename__ = "universes"
    __table_args__ = (
        CheckConstraint("market IN ('US', 'VN')", name="ck_universes_market"),
    )

    id: Mapped[int] = mapped_column(_ID_TYPE, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    market: Mapped[str] = mapped_column(String(2), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    as_of: Mapped[str | None] = mapped_column(String(64))
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    memberships: Mapped[list[UniverseMembership]] = relationship(
        back_populates="universe", cascade="all, delete-orphan"
    )


class UniverseMembership(Base):
    """Current membership of one instrument in one universe snapshot."""

    __tablename__ = "universe_memberships"
    __table_args__ = (
        UniqueConstraint(
            "universe_id", "instrument_id", name="uq_universe_membership"
        ),
    )

    id: Mapped[int] = mapped_column(_ID_TYPE, primary_key=True, autoincrement=True)
    universe_id: Mapped[int] = mapped_column(
        ForeignKey("universes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    universe: Mapped[Universe] = relationship(back_populates="memberships")
    instrument: Mapped[Instrument] = relationship(back_populates="memberships")


class PriceBar(Base):
    """One canonical daily OHLCV observation for an instrument and price basis."""

    __tablename__ = "price_bars"
    __table_args__ = (
        CheckConstraint("open > 0", name="ck_price_bars_open_positive"),
        CheckConstraint("high > 0", name="ck_price_bars_high_positive"),
        CheckConstraint("low > 0", name="ck_price_bars_low_positive"),
        CheckConstraint("close > 0", name="ck_price_bars_close_positive"),
        CheckConstraint("high >= low", name="ck_price_bars_high_gte_low"),
        CheckConstraint("volume IS NULL OR volume >= 0", name="ck_price_bars_volume"),
        CheckConstraint("price_scale > 0", name="ck_price_bars_price_scale"),
        UniqueConstraint(
            "instrument_id",
            "trading_date",
            "price_basis",
            name="uq_price_bars_instrument_date_basis",
        ),
        Index("ix_price_bars_trading_date", "trading_date"),
    )

    id: Mapped[int] = mapped_column(_ID_TYPE, primary_key=True, autoincrement=True)
    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False
    )
    trading_date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    price_scale: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    price_basis: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    instrument: Mapped[Instrument] = relationship(back_populates="price_bars")


class PriceBarCoverage(Base):
    """Pre-aggregated coverage for operational status and refresh planning."""

    __tablename__ = "price_bar_coverages"
    __table_args__ = (
        UniqueConstraint(
            "instrument_id", "price_basis", name="uq_price_bar_coverage_basis"
        ),
        CheckConstraint("row_count > 0", name="ck_price_bar_coverage_rows"),
    )

    id: Mapped[int] = mapped_column(_ID_TYPE, primary_key=True, autoincrement=True)
    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    price_basis: Mapped[str] = mapped_column(String(32), nullable=False)
    first_date: Mapped[date] = mapped_column(Date, nullable=False)
    last_date: Mapped[date] = mapped_column(Date, nullable=False)
    row_count: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    instrument: Mapped[Instrument] = relationship(
        back_populates="price_bar_coverages"
    )


class FundamentalReport(Base):
    """One published report or earnings snapshot with point-in-time availability."""

    __tablename__ = "fundamental_reports"
    __table_args__ = (
        CheckConstraint(
            "period_type IN ('quarterly', 'annual', 'earnings', 'other')",
            name="ck_fundamental_reports_period_type",
        ),
        CheckConstraint(
            "scope IN ('consolidated', 'standalone', 'unknown')",
            name="ck_fundamental_reports_scope",
        ),
        CheckConstraint(
            "fiscal_quarter IS NULL OR fiscal_quarter BETWEEN 1 AND 4",
            name="ck_fundamental_reports_quarter",
        ),
        CheckConstraint(
            "reporting_currency IS NULL OR length(reporting_currency) = 3",
            name="ck_fundamental_reports_currency",
        ),
        UniqueConstraint(
            "instrument_id",
            "source",
            "report_key",
            name="uq_fundamental_report_source_key",
        ),
        Index(
            "ix_fundamental_reports_instrument_effective",
            "instrument_id",
            "effective_session_date",
        ),
        Index(
            "ix_fundamental_reports_instrument_period",
            "instrument_id",
            "period_end",
        ),
    )

    id: Mapped[int] = mapped_column(_ID_TYPE, primary_key=True, autoincrement=True)
    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    report_key: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_report_id: Mapped[str | None] = mapped_column(String(255))
    period_label: Mapped[str | None] = mapped_column(String(100))
    period_end: Mapped[date | None] = mapped_column(Date)
    fiscal_year: Mapped[int | None] = mapped_column(Integer)
    fiscal_quarter: Mapped[int | None] = mapped_column(Integer)
    period_type: Mapped[str] = mapped_column(String(16), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    effective_session_date: Mapped[date] = mapped_column(Date, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reporting_currency: Mapped[str | None] = mapped_column(String(3))
    scope: Mapped[str] = mapped_column(
        String(16), nullable=False, default="consolidated"
    )
    is_restatement: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    raw_payload_hash: Mapped[str | None] = mapped_column(String(64))
    methodology: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    instrument: Mapped[Instrument] = relationship(back_populates="fundamental_reports")
    facts: Mapped[list[FundamentalFact]] = relationship(
        back_populates="report", cascade="all, delete-orphan"
    )


class FundamentalFact(Base):
    """One normalized reported or versioned derived metric from a report."""

    __tablename__ = "fundamental_facts"
    __table_args__ = (
        CheckConstraint(
            "unit IN ('currency', 'shares', 'per_share', 'ratio', 'percent', 'count')",
            name="ck_fundamental_facts_unit",
        ),
        CheckConstraint(
            "period_basis IN ('instant', 'quarter', 'ytd', 'annual', 'ttm')",
            name="ck_fundamental_facts_period_basis",
        ),
        CheckConstraint(
            "fact_kind IN ('reported', 'provider_derived', 'system_derived')",
            name="ck_fundamental_facts_kind",
        ),
        CheckConstraint("scale > 0", name="ck_fundamental_facts_scale"),
        CheckConstraint(
            "currency IS NULL OR length(currency) = 3",
            name="ck_fundamental_facts_currency",
        ),
        UniqueConstraint(
            "report_id",
            "metric_code",
            "period_basis",
            "fact_kind",
            "calculation_version",
            name="uq_fundamental_fact_identity",
        ),
        Index("ix_fundamental_facts_metric", "metric_code"),
    )

    id: Mapped[int] = mapped_column(_ID_TYPE, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(
        ForeignKey("fundamental_reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    metric_code: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(38, 10), nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)
    currency: Mapped[str | None] = mapped_column(String(3))
    scale: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1)
    period_basis: Mapped[str] = mapped_column(String(16), nullable=False)
    fact_kind: Mapped[str] = mapped_column(String(24), nullable=False)
    source_field: Mapped[str | None] = mapped_column(String(255))
    calculation_version: Mapped[str] = mapped_column(
        String(64), nullable=False, default="reported"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    report: Mapped[FundamentalReport] = relationship(back_populates="facts")


class ProviderValuationObservation(Base):
    """Sparse provider-reported valuation used only for comparison and audit."""

    __tablename__ = "provider_valuation_observations"
    __table_args__ = (
        CheckConstraint(
            "unit IN ('currency', 'ratio', 'percent')",
            name="ck_provider_valuation_unit",
        ),
        CheckConstraint("scale > 0", name="ck_provider_valuation_scale"),
        CheckConstraint(
            "currency IS NULL OR length(currency) = 3",
            name="ck_provider_valuation_currency",
        ),
        UniqueConstraint(
            "instrument_id",
            "source",
            "observation_key",
            "metric_code",
            name="uq_provider_valuation_observation",
        ),
        Index(
            "ix_provider_valuation_instrument_effective",
            "instrument_id",
            "effective_session_date",
        ),
    )

    id: Mapped[int] = mapped_column(_ID_TYPE, primary_key=True, autoincrement=True)
    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    observation_key: Mapped[str] = mapped_column(String(255), nullable=False)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    effective_session_date: Mapped[date] = mapped_column(Date, nullable=False)
    metric_code: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(38, 10), nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)
    currency: Mapped[str | None] = mapped_column(String(3))
    scale: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1)
    methodology: Mapped[str | None] = mapped_column(String(1000))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    instrument: Mapped[Instrument] = relationship(
        back_populates="provider_valuation_observations"
    )


class FundamentalRefreshRun(Base):
    """Durable operational record for one universe fundamentals refresh."""

    __tablename__ = "fundamental_refresh_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'completed', 'failed')",
            name="ck_fundamental_refresh_runs_status",
        ),
        CheckConstraint(
            "requested_count >= 0 AND reused_count >= 0 AND "
            "succeeded_count >= 0 AND failed_count >= 0",
            name="ck_fundamental_refresh_runs_counts",
        ),
        Index(
            "ix_fundamental_refresh_runs_universe_started",
            "universe_id",
            "started_at",
        ),
    )

    id: Mapped[int] = mapped_column(_ID_TYPE, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    universe_id: Mapped[int] = mapped_column(
        ForeignKey("universes.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_version: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    requested_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reused_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    succeeded_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_summary: Mapped[dict[str, object] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
