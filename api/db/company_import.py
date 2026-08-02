"""Import current static company universes into PostgreSQL."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from api.db.models import Instrument, Universe, UniverseMembership
from api.db.session import session_scope
from api.symbol_list_data import LIST_FILES, load_static_payload


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
        instrument_rows = _upsert_instruments(session, instruments)
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
            market: int(count)
            for market, count in session.execute(
                select(Instrument.market, func.count(Instrument.id)).group_by(
                    Instrument.market
                )
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
                "source_lists": [],
            })
            current["source_lists"].append(list_id)
            for field in ("company_name", "sector", "industry", "exchange"):
                if not current.get(field) and row.get(field if field != "company_name" else "name"):
                    current[field] = row[field if field != "company_name" else "name"]
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
            row = Universe(code=list_id, market=_market_for(list_id), source=IMPORT_SOURCE)
            session.add(row)
            existing[list_id] = row
        row.name = str(payload["name"])
        row.market = _market_for(list_id)
        row.description = str(payload.get("description") or "")
        row.as_of = str(payload["as_of"]) if payload.get("as_of") else None
        row.fetched_at = _parse_timestamp(payload.get("fetched_at"))
        row.source = IMPORT_SOURCE
    return existing


def _upsert_instruments(
    session: Session,
    values: dict[tuple[str, str], dict[str, Any]],
) -> dict[tuple[str, str], Instrument]:
    markets = {market for market, _ in values}
    existing = {
        (row.market, row.ticker): row
        for row in session.scalars(
            select(Instrument).where(Instrument.market.in_(markets))
        )
    }
    for key, value in values.items():
        row = existing.get(key)
        if row is None:
            row = Instrument(
                market=value["market"],
                ticker=value["ticker"],
                company_name=value["company_name"],
                source=IMPORT_SOURCE,
            )
            session.add(row)
            existing[key] = row
        row.company_name = str(value["company_name"])
        row.sector = _optional_text(value.get("sector"))
        row.industry = _optional_text(value.get("industry"))
        row.exchange = _optional_text(value.get("exchange"))
        row.is_active = True
        row.source = IMPORT_SOURCE
    return existing


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
