"""Initial company and universe persistence model."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
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
