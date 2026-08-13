"""Small PostgreSQL-model fixture for catalog and analysis API tests."""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from api.db.models import (
    Asset,
    AssetIssuer,
    Company,
    CompanyIdentifier,
    Instrument,
    InstrumentSymbol,
    Universe,
    UniverseMembership,
    Venue,
)
from api.equity_venues import EQUITY_VENUES
from api.venue_calendars import venue_calendar


_FETCHED_AT = datetime(2026, 8, 13, tzinfo=UTC)


def seed_company_catalog(session: Session) -> dict[str, Instrument]:
    """Seed a representative canonical catalog without file-backed snapshots."""
    venues = {}
    for definition in EQUITY_VENUES:
        calendar = venue_calendar(definition.code)
        venue = Venue(
            code=definition.code,
            name=definition.name,
            venue_type=definition.venue_type,
            country_code=definition.country_code,
            timezone_name=calendar.timezone_name,
            trading_calendar_code=calendar.trading_calendar_code,
            session_cutoff_time=calendar.session_cutoff_time,
            is_active=True,
            source="test:venue-registry",
        )
        session.add(venue)
        venues[definition.code] = venue

    currencies = {
        "USD": Asset(
            canonical_code="USD",
            name="United States Dollar",
            asset_type="fiat",
            is_active=True,
            source="test",
        ),
        "VND": Asset(
            canonical_code="VND",
            name="Vietnamese Dong",
            asset_type="fiat",
            is_active=True,
            source="test",
        ),
    }
    session.add_all(currencies.values())

    universes = {
        code: Universe(
            code=code,
            name=name,
            description="Canonical test Universe",
            as_of="2026-08-13",
            fetched_at=_FETCHED_AT,
            source="test:universe-sync",
        )
        for code, name in (
            ("US100", "Nasdaq 100"),
            ("US500", "S&P 500"),
            ("US30", "Dow 30"),
            ("VN30", "VN30"),
            ("VN100", "VN100"),
            ("VNALL", "VN All"),
        )
    }
    session.add_all(universes.values())

    instruments: dict[str, Instrument] = {}

    def add_equity(
        ticker: str,
        company_name: str,
        *,
        country: str,
        venue_code: str,
        sector: str,
        industry: str,
        memberships: tuple[str, ...] = (),
        cik: str | None = None,
        company: Company | None = None,
        listing_symbol: str | None = None,
    ) -> Instrument:
        issuer = company or Company(
            display_name=company_name,
            legal_name=company_name,
            country_code=country,
            sector=sector,
            industry=industry,
            is_active=True,
            source="test:universe-sync",
        )
        if company is None:
            session.add(issuer)
        if cik is not None and not issuer.identifiers:
            issuer.identifiers.append(CompanyIdentifier(
                namespace="sec_cik",
                value=cik,
                source="test:universe-sync",
            ))
        currency = "VND" if country == "VN" else "USD"
        asset = Asset(
            canonical_code=f"EQUITY:{venue_code}:{ticker}",
            name=f"{company_name} equity",
            asset_type="equity",
            is_active=True,
            source="test:universe-sync",
        )
        instrument = Instrument(
            company=issuer,
            venue=venues[venue_code],
            base_asset=asset,
            quote_asset=currencies[currency],
            settlement_asset=currencies[currency],
            ticker=ticker,
            instrument_type="common_stock",
            currency=currency,
            is_active=True,
            source="test:universe-sync",
        )
        asset.issuers.append(AssetIssuer(
            company=issuer,
            role="issuer",
            source="test:universe-sync",
        ))
        symbols = {
            "canonical": ticker,
            "listing": listing_symbol or ticker,
        }
        if country == "US":
            symbols["yfinance"] = ticker
        instrument.symbols.extend(
            InstrumentSymbol(
                namespace=namespace,
                symbol=symbol,
                is_primary=True,
                source="test:universe-sync",
            )
            for namespace, symbol in symbols.items()
        )
        instrument.memberships.extend(
            UniverseMembership(
                universe=universes[code],
                source="test:universe-sync",
                fetched_at=_FETCHED_AT,
            )
            for code in memberships
        )
        session.add(instrument)
        instruments[ticker] = instrument
        return instrument

    alphabet = Company(
        display_name="Alphabet Inc.",
        legal_name="Alphabet Inc.",
        country_code="US",
        sector="Communication Services",
        industry="Interactive Media & Services",
        is_active=True,
        source="test:universe-sync",
    )
    session.add(alphabet)
    add_equity(
        "GOOG",
        "Alphabet Inc.",
        country="US",
        venue_code="NASDAQ",
        sector="Communication Services",
        industry="Interactive Media & Services",
        memberships=("US100", "US500"),
        cik="1652044",
        company=alphabet,
    )
    add_equity(
        "GOOGL",
        "Alphabet Inc.",
        country="US",
        venue_code="NASDAQ",
        sector="Communication Services",
        industry="Interactive Media & Services",
        memberships=("US100", "US500"),
        company=alphabet,
    )
    add_equity(
        "AAPL",
        "Apple Inc.",
        country="US",
        venue_code="NASDAQ",
        sector="Information Technology",
        industry="Technology Hardware, Storage & Peripherals",
        memberships=("US100", "US500", "US30"),
    )
    add_equity(
        "MSFT",
        "Microsoft Corporation",
        country="US",
        venue_code="NASDAQ",
        sector="Information Technology",
        industry="Systems Software",
        memberships=("US100", "US500", "US30"),
    )
    add_equity(
        "BRK-B",
        "Berkshire Hathaway Inc.",
        country="US",
        venue_code="NYSE",
        sector="Financials",
        industry="Multi-Sector Holdings",
        memberships=("US500",),
        listing_symbol="BRK.B",
    )
    add_equity(
        "FPT",
        "FPT Corporation",
        country="VN",
        venue_code="HOSE",
        sector="Information Technology",
        industry="IT Services",
        memberships=("VN30", "VN100", "VNALL"),
    )

    for index in range(55):
        add_equity(
            f"T{index:03d}",
            f"Synthetic US Company {index:03d}",
            country="US",
            venue_code="NYSE",
            sector="Industrials",
            industry="Industrial Conglomerates",
        )
    for index in range(5):
        add_equity(
            f"V{index:02d}",
            f"Synthetic VN Company {index:02d}",
            country="VN",
            venue_code="HOSE",
            sector="Industrials",
            industry="Industrial Conglomerates",
        )

    session.flush()
    return instruments
