"""Canonical application persistence models."""
from __future__ import annotations

from datetime import date, datetime, time
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
    Numeric,
    String,
    Time,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


_ID_TYPE = BigInteger().with_variant(Integer, "sqlite")


class Company(Base):
    """Canonical issuer identity shared by one or more tradable instruments."""

    __tablename__ = "companies"
    __table_args__ = (
        CheckConstraint("country_code IN ('US', 'VN')", name="ck_companies_country"),
    )

    id: Mapped[int] = mapped_column(_ID_TYPE, primary_key=True, autoincrement=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    legal_name: Mapped[str | None] = mapped_column(String(255))
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    sector: Mapped[str | None] = mapped_column(String(255))
    industry: Mapped[str | None] = mapped_column(String(255))
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

    identifiers: Mapped[list[CompanyIdentifier]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    instruments: Mapped[list[Instrument]] = relationship(back_populates="company")
    asset_issuers: Mapped[list[AssetIssuer]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )


class CompanyIdentifier(Base):
    """Stable external identifier used to reconcile issuer records."""

    __tablename__ = "company_identifiers"
    __table_args__ = (
        UniqueConstraint("namespace", "value", name="uq_company_identifier"),
    )

    id: Mapped[int] = mapped_column(_ID_TYPE, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    namespace: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    company: Mapped[Company] = relationship(back_populates="identifiers")


class Asset(Base):
    """Canonical economic asset independent from any trading venue."""

    __tablename__ = "assets"
    __table_args__ = (
        CheckConstraint(
            "asset_type IN ('equity', 'crypto', 'fiat', 'stablecoin')",
            name="ck_assets_type",
        ),
        Index(
            "uq_assets_network_contract",
            "network",
            "contract_address",
            unique=True,
            postgresql_where=text("contract_address IS NOT NULL"),
            sqlite_where=text("contract_address IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(_ID_TYPE, primary_key=True, autoincrement=True)
    canonical_code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False)
    network: Mapped[str | None] = mapped_column(String(64))
    contract_address: Mapped[str | None] = mapped_column(String(255))
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

    issuers: Mapped[list[AssetIssuer]] = relationship(
        back_populates="asset", cascade="all, delete-orphan"
    )
    base_instruments: Mapped[list[Instrument]] = relationship(
        back_populates="base_asset", foreign_keys="Instrument.base_asset_id"
    )
    quote_instruments: Mapped[list[Instrument]] = relationship(
        back_populates="quote_asset", foreign_keys="Instrument.quote_asset_id"
    )
    settlement_instruments: Mapped[list[Instrument]] = relationship(
        back_populates="settlement_asset",
        foreign_keys="Instrument.settlement_asset_id",
    )


class AssetIssuer(Base):
    """Effective-dated relationship between an asset and an issuing entity."""

    __tablename__ = "asset_issuers"
    __table_args__ = (
        CheckConstraint(
            "valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from",
            name="ck_asset_issuers_validity",
        ),
        UniqueConstraint(
            "asset_id", "company_id", "role", "valid_from",
            name="uq_asset_issuers_identity",
        ),
        Index(
            "uq_asset_issuers_current",
            "asset_id",
            "company_id",
            "role",
            unique=True,
            postgresql_where=text("valid_to IS NULL"),
            sqlite_where=text("valid_to IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(_ID_TYPE, primary_key=True, autoincrement=True)
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="issuer")
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    asset: Mapped[Asset] = relationship(back_populates="issuers")
    company: Mapped[Company] = relationship(back_populates="asset_issuers")


class Venue(Base):
    """An economic trading venue, distinct from the source supplying data."""

    __tablename__ = "venues"

    id: Mapped[int] = mapped_column(_ID_TYPE, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    venue_type: Mapped[str] = mapped_column(String(32), nullable=False)
    country_code: Mapped[str | None] = mapped_column(String(2))
    timezone_name: Mapped[str] = mapped_column(String(64), nullable=False)
    trading_calendar_code: Mapped[str] = mapped_column(String(64), nullable=False)
    session_cutoff_time: Mapped[time] = mapped_column(Time, nullable=False)
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

    instruments: Mapped[list[Instrument]] = relationship(back_populates="venue")


class Instrument(Base):
    """One venue-specific tradable product over one or more assets."""

    __tablename__ = "instruments"
    __table_args__ = (
        CheckConstraint(
            "instrument_type != 'spot' OR "
            "(company_id IS NULL AND venue_id IS NOT NULL "
            "AND base_asset_id IS NOT NULL AND quote_asset_id IS NOT NULL)",
            name="ck_instruments_spot_identity",
        ),
        CheckConstraint(
            "instrument_type != 'reference_rate' OR "
            "(company_id IS NULL AND venue_id IS NULL "
            "AND base_asset_id IS NOT NULL AND quote_asset_id IS NOT NULL)",
            name="ck_instruments_reference_rate_identity",
        ),
        CheckConstraint(
            "instrument_type != 'market_index' OR "
            "(company_id IS NULL AND venue_id IS NULL "
            "AND base_asset_id IS NULL AND quote_asset_id IS NULL "
            "AND settlement_asset_id IS NULL)",
            name="ck_instruments_market_index_identity",
        ),
        Index(
            "uq_instruments_ticker_without_venue",
            "ticker",
            unique=True,
            postgresql_where=text("venue_id IS NULL"),
            sqlite_where=text("venue_id IS NULL"),
        ),
        Index(
            "uq_instruments_venue_ticker",
            "venue_id",
            "ticker",
            unique=True,
            postgresql_where=text("venue_id IS NOT NULL"),
            sqlite_where=text("venue_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(_ID_TYPE, primary_key=True, autoincrement=True)
    company_id: Mapped[int | None] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), index=True
    )
    venue_id: Mapped[int | None] = mapped_column(
        ForeignKey("venues.id", ondelete="RESTRICT"), index=True
    )
    base_asset_id: Mapped[int | None] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"), index=True
    )
    quote_asset_id: Mapped[int | None] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"), index=True
    )
    settlement_asset_id: Mapped[int | None] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"), index=True
    )
    # Compatibility/current-identity column. Full aliases and history live in
    # instrument_symbols; existing price and API callers can continue using it.
    ticker: Mapped[str] = mapped_column(String(64), nullable=False)
    instrument_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="common_stock"
    )
    share_class: Mapped[str | None] = mapped_column(String(64))
    currency: Mapped[str] = mapped_column(String(16), nullable=False)
    base_precision: Mapped[int | None] = mapped_column(Integer)
    quote_precision: Mapped[int | None] = mapped_column(Integer)
    price_tick_size: Mapped[Decimal | None] = mapped_column(Numeric(38, 18))
    quantity_step_size: Mapped[Decimal | None] = mapped_column(Numeric(38, 18))
    minimum_quantity: Mapped[Decimal | None] = mapped_column(Numeric(38, 18))
    minimum_notional: Mapped[Decimal | None] = mapped_column(Numeric(38, 18))
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

    company: Mapped[Company | None] = relationship(back_populates="instruments")
    venue: Mapped[Venue | None] = relationship(back_populates="instruments")
    base_asset: Mapped[Asset | None] = relationship(
        back_populates="base_instruments", foreign_keys=[base_asset_id]
    )
    quote_asset: Mapped[Asset | None] = relationship(
        back_populates="quote_instruments", foreign_keys=[quote_asset_id]
    )
    settlement_asset: Mapped[Asset | None] = relationship(
        back_populates="settlement_instruments", foreign_keys=[settlement_asset_id]
    )
    symbols: Mapped[list[InstrumentSymbol]] = relationship(
        back_populates="instrument", cascade="all, delete-orphan"
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
    price_refresh_states: Mapped[list[PriceRefreshState]] = relationship(
        back_populates="instrument", cascade="all, delete-orphan"
    )
    fundamental_reports: Mapped[list[FundamentalReport]] = relationship(
        back_populates="instrument", cascade="all, delete-orphan"
    )
    provider_valuation_observations: Mapped[list[ProviderValuationObservation]] = relationship(
        back_populates="instrument", cascade="all, delete-orphan"
    )
    watchlist_memberships: Mapped[list[WatchlistMembership]] = relationship(
        back_populates="instrument",
        cascade="all, delete-orphan",
        foreign_keys="WatchlistMembership.instrument_id",
    )


class InstrumentSymbol(Base):
    """A canonical, source-specific, or historical symbol for an instrument."""

    __tablename__ = "instrument_symbols"
    __table_args__ = (
        CheckConstraint(
            "valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from",
            name="ck_instrument_symbols_validity",
        ),
        Index(
            "ix_instrument_symbols_current_lookup",
            "namespace",
            "symbol",
            postgresql_where=text("valid_to IS NULL"),
            sqlite_where=text("valid_to IS NULL"),
        ),
        Index(
            "uq_instrument_symbols_current_primary",
            "instrument_id",
            "namespace",
            unique=True,
            postgresql_where=text("valid_to IS NULL AND is_primary"),
            sqlite_where=text("valid_to IS NULL AND is_primary"),
        ),
    )

    id: Mapped[int] = mapped_column(_ID_TYPE, primary_key=True, autoincrement=True)
    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    namespace: Mapped[str] = mapped_column(String(64), nullable=False)
    symbol: Mapped[str] = mapped_column(String(64), nullable=False)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
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

    instrument: Mapped[Instrument] = relationship(back_populates="symbols")


class Universe(Base):
    """A named current constituent universe such as US500 or VN30."""

    __tablename__ = "universes"

    id: Mapped[int] = mapped_column(_ID_TYPE, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
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


class UniverseSyncRun(Base):
    """Scalar audit record for one attempted live Universe synchronization."""

    __tablename__ = "universe_sync_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('succeeded', 'failed')",
            name="ck_universe_sync_runs_status",
        ),
        Index(
            "ix_universe_sync_runs_universe_started",
            "universe_code",
            "started_at",
        ),
    )

    id: Mapped[int] = mapped_column(_ID_TYPE, primary_key=True, autoincrement=True)
    universe_code: Mapped[str] = mapped_column(String(16), nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    finished_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    effective_date: Mapped[date | None] = mapped_column(Date)
    received_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    added_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    removed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unchanged_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(String(2000))


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
    currency: Mapped[str] = mapped_column(String(16), nullable=False)
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


class PriceRefreshState(Base):
    """Latest provider-check outcome, separate from the latest traded bar."""

    __tablename__ = "price_refresh_states"
    __table_args__ = (
        UniqueConstraint(
            "instrument_id", "price_basis", name="uq_price_refresh_state_basis"
        ),
        CheckConstraint(
            "outcome IN ('current', 'checked_no_new_bar', 'failed')",
            name="ck_price_refresh_states_outcome",
        ),
    )

    id: Mapped[int] = mapped_column(_ID_TYPE, primary_key=True, autoincrement=True)
    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    price_basis: Mapped[str] = mapped_column(String(32), nullable=False)
    attempted_through: Mapped[date] = mapped_column(Date, nullable=False)
    returned_through: Mapped[date | None] = mapped_column(Date)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    primary_source: Mapped[str] = mapped_column(String(100), nullable=False)
    selected_source: Mapped[str | None] = mapped_column(String(100))
    detail: Mapped[str | None] = mapped_column(String(1000))
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    instrument: Mapped[Instrument] = relationship(
        back_populates="price_refresh_states"
    )


class Watchlist(Base):
    """One user-managed, ordered collection of canonical instruments."""

    __tablename__ = "watchlists"
    __table_args__ = (
        UniqueConstraint("name_key", name="uq_watchlists_name_key"),
    )

    id: Mapped[int] = mapped_column(_ID_TYPE, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    name_key: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    memberships: Mapped[list[WatchlistMembership]] = relationship(
        back_populates="watchlist",
        cascade="all, delete-orphan",
        foreign_keys="WatchlistMembership.watchlist_id",
    )


class WatchlistMembership(Base):
    """Ordered membership of a canonical instrument in a watchlist."""

    __tablename__ = "watchlist_memberships"
    __table_args__ = (
        CheckConstraint("position >= 0", name="ck_watchlist_memberships_position"),
        UniqueConstraint(
            "watchlist_id", "instrument_id", name="uq_watchlist_membership"
        ),
    )

    id: Mapped[int] = mapped_column(_ID_TYPE, primary_key=True, autoincrement=True)
    watchlist_id: Mapped[int] = mapped_column(
        ForeignKey("watchlists.id", ondelete="CASCADE"), nullable=False, index=True
    )
    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    watchlist: Mapped[Watchlist] = relationship(
        back_populates="memberships", foreign_keys=[watchlist_id]
    )
    instrument: Mapped[Instrument] = relationship(
        back_populates="watchlist_memberships", foreign_keys=[instrument_id]
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
