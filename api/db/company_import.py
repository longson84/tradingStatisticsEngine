"""Import current static company universes into PostgreSQL."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session, selectinload

from api.db.models import (
    Company,
    CompanyIdentifier,
    Instrument,
    InstrumentSymbol,
    Universe,
    UniverseMembership,
    Venue,
)
from api.db.session import session_scope
from api.equity_venues import (
    EQUITY_VENUES,
    EQUITY_VENUE_SOURCE,
    canonical_equity_venue_code,
)
from api.symbol_list_data import LIST_FILES, load_static_payload
from api.venue_calendars import venue_calendar


IMPORT_SOURCE = "static-symbol-list"


@dataclass(frozen=True)
class UniverseImportResult:
    universe: str
    expected_members: int
    stored_members: int


@dataclass(frozen=True)
class CompanyImportResult:
    instruments: int
    markets: dict[str, int]
    universes: tuple[UniverseImportResult, ...]


def import_company_universes(engine: Engine) -> CompanyImportResult:
    """Idempotently synchronize all saved constituent snapshots."""
    payloads = {
        list_id: load_static_payload(list_id)
        for list_id in LIST_FILES
    }
    instruments, memberships = _merge_instruments(payloads)

    with session_scope(engine) as session:
        universe_rows = _upsert_universes(session, payloads)
        venue_rows = _upsert_equity_venues(session)
        instrument_rows = _upsert_companies_and_instruments(
            session,
            instruments,
            venue_rows,
        )
        session.flush()
        _sync_memberships(
            session,
            payloads,
            memberships,
            universe_rows,
            instrument_rows,
        )

    return verify_company_universes(engine, payloads=payloads)


def verify_company_universes(
    engine: Engine,
    *,
    payloads: dict[str, dict[str, Any]] | None = None,
) -> CompanyImportResult:
    """Compare database membership counts with the canonical snapshots."""
    payloads = payloads or {
        list_id: load_static_payload(list_id)
        for list_id in LIST_FILES
    }
    with Session(engine) as session:
        instruments = int(session.scalar(select(func.count(Instrument.id))) or 0)
        markets = {
            country: int(count)
            for country, count in session.execute(
                select(Venue.country_code, func.count(Instrument.id))
                .join(Instrument, Instrument.venue_id == Venue.id)
                .where(Instrument.instrument_type == "common_stock")
                .group_by(Venue.country_code)
            )
        }
        universe_counts = {
            code: int(count)
            for code, count in session.execute(
                select(Universe.code, func.count(UniverseMembership.id))
                .join(UniverseMembership)
                .group_by(Universe.code)
            )
        }
    results = tuple(
        UniverseImportResult(
            universe=list_id,
            expected_members=len(payload.get("symbols", [])),
            stored_members=universe_counts.get(list_id, 0),
        )
        for list_id, payload in payloads.items()
    )
    return CompanyImportResult(
        instruments=instruments,
        markets=markets,
        universes=results,
    )


def _merge_instruments(
    payloads: dict[str, dict[str, Any]],
) -> tuple[dict[tuple[str, str], dict[str, Any]], dict[str, set[tuple[str, str]]]]:
    instruments: dict[tuple[str, str], dict[str, Any]] = {}
    memberships: dict[str, set[tuple[str, str]]] = {}
    for list_id, payload in payloads.items():
        market = _market_for(list_id)
        members: set[tuple[str, str]] = set()
        for row in payload.get("symbols", []):
            ticker = str(row.get("yfinance_symbol") or row["symbol"]).upper().strip()
            key = (market, ticker)
            members.add(key)
            current = instruments.setdefault(key, {
                "market": market,
                "ticker": ticker,
                "company_name": str(row.get("name") or ticker),
                "sector": row.get("sector"),
                "industry": row.get("industry"),
                "exchange": row.get("exchange"),
                "raw_symbol": str(row["symbol"]).upper().strip(),
                "yfinance_symbol": _optional_text(row.get("yfinance_symbol")),
                "sec_cik": _optional_text(row.get("cik")),
                "source_lists": [],
            })
            current["source_lists"].append(list_id)
            for field in ("company_name", "sector", "industry", "exchange"):
                if not current.get(field) and row.get(field if field != "company_name" else "name"):
                    current[field] = row[field if field != "company_name" else "name"]
            if not current.get("sec_cik") and row.get("cik") is not None:
                current["sec_cik"] = str(row["cik"])
            if not current.get("raw_symbol"):
                current["raw_symbol"] = str(row["symbol"]).upper().strip()
            if not current.get("yfinance_symbol") and row.get("yfinance_symbol"):
                current["yfinance_symbol"] = str(row["yfinance_symbol"]).upper().strip()
        memberships[list_id] = members
    return instruments, memberships


def _upsert_universes(
    session: Session,
    payloads: dict[str, dict[str, Any]],
) -> dict[str, Universe]:
    existing = {
        row.code: row
        for row in session.scalars(
            select(Universe).where(Universe.code.in_(payloads))
        )
    }
    for list_id, payload in payloads.items():
        row = existing.get(list_id)
        if row is None:
            row = Universe(code=list_id, source=IMPORT_SOURCE)
            session.add(row)
            existing[list_id] = row
        row.name = str(payload["name"])
        row.description = str(payload.get("description") or "")
        row.as_of = str(payload["as_of"]) if payload.get("as_of") else None
        row.fetched_at = _parse_timestamp(payload.get("fetched_at"))
        row.source = IMPORT_SOURCE
    return existing


def _upsert_companies_and_instruments(
    session: Session,
    values: dict[tuple[str, str], dict[str, Any]],
    venues: dict[str, Venue],
) -> dict[tuple[str, str], Instrument]:
    existing = {
        (
            row.venue.country_code if row.venue is not None
            else row.company.country_code,
            row.ticker,
        ): row
        for row in session.scalars(
            select(Instrument)
            .join(Instrument.company)
            .outerjoin(Instrument.venue)
            .where(
                Company.country_code.in_({market for market, _ in values}),
                Instrument.instrument_type == "common_stock",
            )
            .options(
                selectinload(Instrument.company),
                selectinload(Instrument.symbols),
                selectinload(Instrument.venue),
            )
        )
    }
    companies_by_identifier = {
        (identifier.namespace, identifier.value): identifier.company
        for identifier in session.scalars(
            select(CompanyIdentifier).options(selectinload(CompanyIdentifier.company))
        )
    }
    batch_companies: dict[tuple[str, ...], Company] = {}
    for key, value in values.items():
        row = existing.get(key)
        cik = _optional_text(value.get("sec_cik"))
        company_key = ("sec_cik", cik) if cik else ("instrument", *key)
        company = (
            companies_by_identifier.get(("sec_cik", cik)) if cik else None
        )
        if company is None:
            company = batch_companies.get(company_key)
        if company is None and row is not None:
            company = row.company
        if company is None:
            company = Company(
                display_name=str(value["company_name"]),
                legal_name=str(value["company_name"]),
                country_code=value["market"],
                source=IMPORT_SOURCE,
            )
            session.add(company)
        batch_companies[company_key] = company
        company.display_name = _prefer_company_name(
            company.display_name, str(value["company_name"])
        )
        company.legal_name = company.legal_name or str(value["company_name"])
        company.country_code = value["market"]
        company.sector = _optional_text(value.get("sector")) or company.sector
        company.industry = _optional_text(value.get("industry")) or company.industry
        company.is_active = True
        company.source = IMPORT_SOURCE

        if cik and ("sec_cik", cik) not in companies_by_identifier:
            identifier = CompanyIdentifier(
                company=company,
                namespace="sec_cik",
                value=cik,
                source=IMPORT_SOURCE,
            )
            session.add(identifier)
            companies_by_identifier[("sec_cik", cik)] = company

        if row is None:
            row = Instrument(
                company=company,
                ticker=value["ticker"],
                instrument_type="common_stock",
                currency="VND" if value["market"] == "VN" else "USD",
                source=IMPORT_SOURCE,
            )
            session.add(row)
            existing[key] = row
        row.company = company
        imported_exchange = _optional_text(value.get("exchange"))
        if imported_exchange is not None:
            venue_code = canonical_equity_venue_code(
                value["market"],
                imported_exchange,
            )
            if venue_code is None:
                raise ValueError(
                    "Unsupported equity exchange from static company import: "
                    f"market={value['market']} exchange={imported_exchange}"
                )
            row.venue = venues[venue_code]
        row.currency = "VND" if value["market"] == "VN" else "USD"
        row.is_active = True
        row.source = IMPORT_SOURCE
        _upsert_symbols(session, row, value)
    return existing


def _upsert_equity_venues(session: Session) -> dict[str, Venue]:
    codes = {row.code for row in EQUITY_VENUES}
    venues = {
        row.code: row
        for row in session.scalars(select(Venue).where(Venue.code.in_(codes)))
    }
    for definition in EQUITY_VENUES:
        schedule = venue_calendar(definition.code)
        venue = venues.get(definition.code)
        if venue is None:
            venue = Venue(code=definition.code)
            session.add(venue)
            venues[definition.code] = venue
        venue.name = definition.name
        venue.venue_type = definition.venue_type
        venue.country_code = definition.country_code
        venue.timezone_name = schedule.timezone_name
        venue.trading_calendar_code = schedule.trading_calendar_code
        venue.session_cutoff_time = schedule.session_cutoff_time
        venue.is_active = True
        venue.source = EQUITY_VENUE_SOURCE
    return venues


def _upsert_symbols(
    session: Session,
    instrument: Instrument,
    value: dict[str, Any],
) -> None:
    desired = {
        ("canonical", str(value["ticker"]).upper().strip()),
        ("listing", str(value["raw_symbol"]).upper().strip()),
    }
    yfinance_symbol = _optional_text(value.get("yfinance_symbol"))
    if yfinance_symbol:
        desired.add(("yfinance", yfinance_symbol.upper()))
    existing = {
        (symbol.namespace, symbol.symbol): symbol
        for symbol in instrument.symbols
        if symbol.valid_to is None
    }
    for namespace, symbol_value in desired:
        symbol = existing.get((namespace, symbol_value))
        if symbol is None:
            symbol = InstrumentSymbol(
                instrument=instrument,
                namespace=namespace,
                symbol=symbol_value,
                is_primary=True,
                source=IMPORT_SOURCE,
            )
            session.add(symbol)
        else:
            symbol.is_primary = True
            symbol.source = IMPORT_SOURCE


def _prefer_company_name(current: str, candidate: str) -> str:
    """Prefer a neutral issuer name over an instrument share-class label."""
    current_has_class = "(Class " in current
    candidate_has_class = "(Class " in candidate
    if current_has_class and not candidate_has_class:
        return candidate
    if not current_has_class and candidate_has_class:
        return current
    return candidate or current


def _sync_memberships(
    session: Session,
    payloads: dict[str, dict[str, Any]],
    memberships: dict[str, set[tuple[str, str]]],
    universes: dict[str, Universe],
    instruments: dict[tuple[str, str], Instrument],
) -> None:
    session.flush()
    for list_id, member_keys in memberships.items():
        universe = universes[list_id]
        existing = {
            row.instrument_id: row
            for row in session.scalars(
                select(UniverseMembership).where(
                    UniverseMembership.universe_id == universe.id
                )
            )
        }
        target_ids = {instruments[key].id for key in member_keys}
        for instrument_id, row in existing.items():
            if instrument_id not in target_ids:
                session.delete(row)
        fetched_at = _parse_timestamp(payloads[list_id].get("fetched_at"))
        for instrument_id in target_ids:
            row = existing.get(instrument_id)
            if row is None:
                row = UniverseMembership(
                    universe_id=universe.id,
                    instrument_id=instrument_id,
                    source=IMPORT_SOURCE,
                )
                session.add(row)
            row.source = IMPORT_SOURCE
            row.fetched_at = fetched_at


def _market_for(list_id: str) -> str:
    return "VN" if list_id.startswith("VN") else "US"


def _parse_timestamp(value: object) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
