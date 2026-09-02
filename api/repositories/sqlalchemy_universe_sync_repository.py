"""Transactional SQLAlchemy writer for current equity Universe snapshots."""
from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy import Engine, delete, select, text, update
from sqlalchemy.orm import Session, selectinload

from api.db.models import (
    Asset,
    AssetIssuer,
    Company,
    CompanyIdentifier,
    Instrument,
    InstrumentSymbol,
    Universe,
    UniverseMembership,
    UniverseSyncRun,
    Venue,
)
from api.equity_venues import EQUITY_VENUES, EQUITY_VENUES_BY_CODE, EQUITY_VENUE_SOURCE
from api.repositories.universe_sync_repository import (
    UniverseSyncMember,
    UniverseSyncRejectedError,
    UniverseSyncResult,
    UniverseSyncSnapshot,
)
from api.venue_calendars import venue_calendar
from api.instrument_symbols import canonical_symbol, canonical_symbol_expression, new_instrument


_EXPECTED_MEMBER_RANGES = {
    "US30": (25, 35),
    "US100": (80, 120),
    "US1000": (900, 1_150),
    "US500": (450, 550),
    "US2000": (1_500, 2_500),
    "US3000": (2_400, 3_200),
    "VN30": (25, 35),
    "VNMID": (50, 100),
    "VN100": (80, 130),
    "VNSML": (100, 400),
    "VNALL": (200, 500),
}
_MAX_MEMBERSHIP_CHANGE_FRACTION = 0.35
_SYNC_RUN_RETENTION_PER_UNIVERSE = 100


class SqlAlchemyUniverseSyncRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def preview(
        self,
        snapshots: tuple[UniverseSyncSnapshot, ...],
        *,
        force: bool,
    ) -> tuple[UniverseSyncResult, ...]:
        with Session(self._engine) as session:
            results = self._preview_in_session(session, snapshots)
            self._validate_changes(snapshots, results, force=force)
            return results

    def synchronize(
        self,
        snapshots: tuple[UniverseSyncSnapshot, ...],
        *,
        force: bool,
        started_at: datetime,
    ) -> tuple[UniverseSyncResult, ...]:
        with Session(self._engine) as session, session.begin():
            self._lock_universes(session, snapshots)
            results = self._preview_in_session(session, snapshots)
            self._validate_changes(snapshots, results, force=force)
            self._apply_snapshots(session, snapshots)
            finished_at = datetime.now(UTC)
            for snapshot, result in zip(snapshots, results, strict=True):
                session.add(UniverseSyncRun(
                    universe_code=snapshot.code,
                    source=snapshot.source,
                    status="succeeded",
                    started_at=started_at,
                    finished_at=finished_at,
                    effective_date=snapshot.effective_date,
                    received_count=result.received_count,
                    added_count=result.added_count,
                    removed_count=result.removed_count,
                    unchanged_count=result.unchanged_count,
                ))
            session.flush()
            self._prune_sync_runs(
                session,
                tuple(snapshot.code for snapshot in snapshots),
            )
            return results

    def record_failures(
        self,
        *,
        universe_codes: tuple[str, ...],
        source: str,
        started_at: datetime,
        error: str,
    ) -> None:
        finished_at = datetime.now(UTC)
        with Session(self._engine) as session, session.begin():
            for code in universe_codes:
                session.add(UniverseSyncRun(
                    universe_code=code,
                    source=source,
                    status="failed",
                    started_at=started_at,
                    finished_at=finished_at,
                    received_count=0,
                    added_count=0,
                    removed_count=0,
                    unchanged_count=0,
                    error=error[:2000],
                ))
            session.flush()
            self._prune_sync_runs(session, universe_codes)

    @staticmethod
    def _prune_sync_runs(session: Session, universe_codes: tuple[str, ...]) -> None:
        for code in set(universe_codes):
            expired_ids = tuple(session.scalars(
                select(UniverseSyncRun.id)
                .where(UniverseSyncRun.universe_code == code)
                .order_by(
                    UniverseSyncRun.started_at.desc(),
                    UniverseSyncRun.id.desc(),
                )
                .offset(_SYNC_RUN_RETENTION_PER_UNIVERSE)
            ))
            if expired_ids:
                session.execute(
                    delete(UniverseSyncRun).where(UniverseSyncRun.id.in_(expired_ids))
                )

    def _preview_in_session(
        self,
        session: Session,
        snapshots: tuple[UniverseSyncSnapshot, ...],
    ) -> tuple[UniverseSyncResult, ...]:
        current = self._current_members(session, tuple(row.code for row in snapshots))
        results = []
        for snapshot in snapshots:
            target = {member.symbol: member for member in snapshot.members}
            stored = current.get(snapshot.code, {})
            target_symbols = set(target)
            stored_symbols = set(stored)
            shared = target_symbols & stored_symbols
            metadata_changes = sum(
                self._metadata_changed(stored[symbol], target[symbol])
                for symbol in shared
            )
            results.append(UniverseSyncResult(
                universe_code=snapshot.code,
                received_count=len(target),
                added_count=len(target_symbols - stored_symbols),
                removed_count=len(stored_symbols - target_symbols),
                unchanged_count=len(shared),
                metadata_change_count=metadata_changes,
            ))
        return tuple(results)

    @staticmethod
    def _current_members(
        session: Session,
        codes: tuple[str, ...],
    ) -> dict[str, dict[str, tuple[str, str | None, str | None, str | None]]]:
        rows = session.execute(
            select(
                Universe.code,
                canonical_symbol_expression(),
                Company.display_name,
                Company.sector,
                Company.industry,
                Venue.code,
            )
            .join(UniverseMembership, UniverseMembership.universe_id == Universe.id)
            .join(Instrument, Instrument.id == UniverseMembership.instrument_id)
            .join(Company, Company.id == Instrument.company_id)
            .outerjoin(Venue, Venue.id == Instrument.venue_id)
            .where(Universe.code.in_(codes))
        )
        values: dict[
            str, dict[str, tuple[str, str | None, str | None, str | None]]
        ] = defaultdict(dict)
        for code, symbol, name, sector, industry, venue_code in rows:
            values[code][symbol] = (name, sector, industry, venue_code)
        return dict(values)

    @staticmethod
    def _metadata_changed(
        current: tuple[str, str | None, str | None, str | None],
        target: UniverseSyncMember,
    ) -> bool:
        name, sector, industry, venue_code = current
        return any((
            bool(target.company_name and target.company_name != name),
            bool(target.sector and target.sector != sector),
            bool(target.industry and target.industry != industry),
            target.venue_code != venue_code,
        ))

    @staticmethod
    def _validate_changes(
        snapshots: tuple[UniverseSyncSnapshot, ...],
        results: tuple[UniverseSyncResult, ...],
        *,
        force: bool,
    ) -> None:
        for snapshot, result in zip(snapshots, results, strict=True):
            expected_range = _EXPECTED_MEMBER_RANGES.get(snapshot.code)
            if expected_range is not None and not (
                expected_range[0] <= result.received_count <= expected_range[1]
            ):
                raise UniverseSyncRejectedError(
                    f"{snapshot.code} received {result.received_count} members; "
                    f"expected {expected_range[0]}-{expected_range[1]}"
                )
            for member in snapshot.members:
                venue = EQUITY_VENUES_BY_CODE.get(member.venue_code)
                if (
                    venue is None
                    or venue.country_code != snapshot.listing_country_code
                ):
                    raise UniverseSyncRejectedError(
                        f"{snapshot.code} member {member.symbol} has a cross-country "
                        f"or unknown Venue {member.venue_code!r}"
                    )
            previous_count = result.removed_count + result.unchanged_count
            changed_count = result.added_count + result.removed_count
            if (
                not force
                and previous_count
                and changed_count / previous_count
                > _MAX_MEMBERSHIP_CHANGE_FRACTION
            ):
                raise UniverseSyncRejectedError(
                    f"{snapshot.code} changes {changed_count}/{previous_count} "
                    "members; rerun with --force after reviewing the diff"
                )

    def _apply_snapshots(
        self,
        session: Session,
        snapshots: tuple[UniverseSyncSnapshot, ...],
    ) -> None:
        venues = self._upsert_venues(session)
        quote_assets = self._upsert_quote_assets(session)
        session.flush()
        instruments = session.scalars(
            select(Instrument)
            .where(Instrument.instrument_type == "common_stock")
            .options(
                selectinload(Instrument.company),
                selectinload(Instrument.venue),
                selectinload(Instrument.symbols),
                selectinload(Instrument.base_asset),
            )
        ).all()
        exact, unvenued = self._instrument_indexes(instruments)
        companies_by_identifier = {
            (row.namespace, row.value): row.company
            for row in session.scalars(
                select(CompanyIdentifier).options(
                    selectinload(CompanyIdentifier.company)
                )
            )
        }
        current_issuers = defaultdict(list)
        for issuer in session.scalars(select(AssetIssuer)):
            current_issuers[issuer.asset_id].append(issuer)

        universe_rows = {
            row.code: row
            for row in session.scalars(
                select(Universe).where(
                    Universe.code.in_([snapshot.code for snapshot in snapshots])
                )
            )
        }
        target_members: dict[str, set[int]] = {}
        for snapshot in snapshots:
            universe = universe_rows.get(snapshot.code)
            if universe is None:
                universe = Universe(code=snapshot.code, source=snapshot.source)
                session.add(universe)
                universe_rows[snapshot.code] = universe
            universe.name = snapshot.name
            universe.description = snapshot.description
            universe.as_of = (
                snapshot.effective_date.isoformat()
                if snapshot.effective_date is not None
                else None
            )
            universe.fetched_at = snapshot.fetched_at
            universe.source = snapshot.source

            member_ids: set[int] = set()
            for member in snapshot.members:
                instrument = exact.get((member.venue_code, member.symbol))
                if instrument is None:
                    candidates = unvenued.get(member.symbol, ())
                    if len(candidates) == 1:
                        instrument = candidates[0]
                identifier_companies = {
                    companies_by_identifier[(identifier.namespace, identifier.value)]
                    for identifier in member.identifiers
                    if (identifier.namespace, identifier.value) in companies_by_identifier
                }
                if len(identifier_companies) > 1:
                    raise UniverseSyncRejectedError(
                        f"Stable identifiers for {member.symbol} resolve to "
                        "different Companies"
                    )
                identified_company = next(iter(identifier_companies), None)
                company = identified_company or (
                    instrument.company if instrument is not None else None
                )
                if company is None:
                    company = Company(
                        display_name=member.company_name,
                        legal_name=member.company_name,
                        domicile_country_code=None,
                        source=snapshot.source,
                    )
                    session.add(company)
                self._update_company(company, member, snapshot)
                for identifier in member.identifiers:
                    key = (identifier.namespace, identifier.value)
                    existing_company = companies_by_identifier.get(key)
                    if existing_company is not None and existing_company is not company:
                        raise UniverseSyncRejectedError(
                            f"Identifier {identifier.namespace}:{identifier.value} "
                            "already belongs to another Company"
                        )
                    if existing_company is None:
                        session.add(CompanyIdentifier(
                            company=company,
                            namespace=identifier.namespace,
                            value=identifier.value,
                            source=snapshot.source,
                        ))
                        companies_by_identifier[key] = company

                if instrument is None:
                    currency = EQUITY_VENUES_BY_CODE[member.venue_code].currency_code
                    instrument = new_instrument(
                        member.symbol,
                        source=snapshot.source,
                        company=company,
                        venue=venues[member.venue_code],
                        instrument_type="common_stock",
                        currency=currency,
                    )
                    session.add(instrument)
                    session.flush()
                    exact[(member.venue_code, member.symbol)] = instrument
                else:
                    instrument.company = company
                    instrument.venue = venues[member.venue_code]
                instrument.currency = EQUITY_VENUES_BY_CODE[
                    member.venue_code
                ].currency_code
                instrument.quote_asset = quote_assets[instrument.currency]
                instrument.settlement_asset = quote_assets[instrument.currency]
                instrument.is_active = True
                instrument.source = snapshot.source
                self._ensure_equity_asset(
                    session,
                    instrument,
                    company,
                    snapshot,
                    current_issuers,
                )
                self._upsert_symbol(
                    session,
                    instrument,
                    namespace="canonical",
                    symbol=member.symbol,
                    snapshot=snapshot,
                )
                self._upsert_symbol(
                    session,
                    instrument,
                    namespace="listing",
                    symbol=member.listing_symbol,
                    snapshot=snapshot,
                )
                self._upsert_symbol(
                    session,
                    instrument,
                    namespace=snapshot.source,
                    symbol=member.listing_symbol,
                    snapshot=snapshot,
                )
                session.flush()
                member_ids.add(instrument.id)
            target_members[snapshot.code] = member_ids

        session.flush()
        for snapshot in snapshots:
            universe = universe_rows[snapshot.code]
            existing = {
                row.instrument_id: row
                for row in session.scalars(
                    select(UniverseMembership).where(
                        UniverseMembership.universe_id == universe.id
                    )
                )
            }
            for instrument_id, membership in existing.items():
                if instrument_id not in target_members[snapshot.code]:
                    session.delete(membership)
            for instrument_id in target_members[snapshot.code]:
                membership = existing.get(instrument_id)
                if membership is None:
                    membership = UniverseMembership(
                        universe=universe,
                        instrument_id=instrument_id,
                        source=snapshot.source,
                    )
                    session.add(membership)
                membership.source = snapshot.source
                membership.fetched_at = snapshot.fetched_at
        session.flush()
        self._recalculate_active_state(session)

    @staticmethod
    def _instrument_indexes(
        instruments: list[Instrument],
    ) -> tuple[
        dict[tuple[str, str], Instrument],
        dict[str, tuple[Instrument, ...]],
    ]:
        exact: dict[tuple[str, str], Instrument] = {}
        unvenued_lists: dict[str, list[Instrument]] = defaultdict(list)
        for instrument in instruments:
            symbols = {
                canonical_symbol(instrument),
                *(row.symbol for row in instrument.symbols if row.valid_to is None),
            }
            if instrument.venue is not None:
                for symbol in symbols:
                    exact[(instrument.venue.code, symbol)] = instrument
            else:
                for symbol in symbols:
                    unvenued_lists[symbol].append(instrument)
        return exact, {
            key: tuple(values) for key, values in unvenued_lists.items()
        }

    @staticmethod
    def _update_company(
        company: Company,
        member: UniverseSyncMember,
        snapshot: UniverseSyncSnapshot,
    ) -> None:
        company.display_name = _prefer_company_name(
            company.display_name,
            member.company_name,
        )
        company.legal_name = company.legal_name or member.company_name
        company.sector = member.sector or company.sector
        company.industry = member.industry or company.industry
        company.is_active = True
        company.source = snapshot.source

    @staticmethod
    def _ensure_equity_asset(
        session: Session,
        instrument: Instrument,
        company: Company,
        snapshot: UniverseSyncSnapshot,
        current_issuers: dict[int, list[AssetIssuer]],
    ) -> None:
        asset = instrument.base_asset
        if asset is None:
            asset = Asset(
                canonical_code=(
                    f"EQUITY:{snapshot.listing_country_code}:{instrument.id}"
                ),
                name=member_name(company, instrument),
                asset_type="equity",
                source=snapshot.source,
            )
            session.add(asset)
            instrument.base_asset = asset
            session.flush()
        asset.name = member_name(company, instrument)
        asset.is_active = True
        active_issuers = [
            row for row in current_issuers.get(asset.id, ()) if row.valid_to is None
        ]
        if not any(row.company_id == company.id for row in active_issuers):
            transition_date = snapshot.effective_date or snapshot.fetched_at.date()
            for row in active_issuers:
                row.valid_to = transition_date
            issuer = AssetIssuer(
                asset=asset,
                company=company,
                role="issuer",
                valid_from=transition_date,
                source=snapshot.source,
            )
            session.add(issuer)
            current_issuers[asset.id].append(issuer)

    @staticmethod
    def _upsert_symbol(
        session: Session,
        instrument: Instrument,
        *,
        namespace: str,
        symbol: str,
        snapshot: UniverseSyncSnapshot,
    ) -> None:
        current = [
            row
            for row in instrument.symbols
            if row.namespace == namespace and row.valid_to is None
        ]
        if any(row.symbol == symbol for row in current):
            return
        transition_date = snapshot.effective_date or snapshot.fetched_at.date()
        for row in current:
            row.valid_to = transition_date
        row = InstrumentSymbol(
            instrument=instrument,
            namespace=namespace[:64],
            symbol=symbol,
            valid_from=transition_date,
            is_primary=True,
            source=snapshot.source,
        )
        session.add(row)

    @staticmethod
    def _upsert_venues(session: Session) -> dict[str, Venue]:
        existing = {
            row.code: row for row in session.scalars(select(Venue))
        }
        for definition in EQUITY_VENUES:
            schedule = venue_calendar(definition.code)
            venue = existing.get(definition.code)
            if venue is None:
                venue = Venue(code=definition.code)
                session.add(venue)
                existing[definition.code] = venue
            venue.name = definition.name
            venue.venue_type = definition.venue_type
            venue.country_code = definition.country_code
            venue.timezone_name = schedule.timezone_name
            venue.trading_calendar_code = schedule.trading_calendar_code
            venue.session_cutoff_time = schedule.session_cutoff_time
            venue.is_active = True
            venue.source = EQUITY_VENUE_SOURCE
        return existing

    @staticmethod
    def _upsert_quote_assets(session: Session) -> dict[str, Asset]:
        currency_codes = {row.currency_code for row in EQUITY_VENUES}
        assets = {
            row.canonical_code: row
            for row in session.scalars(
                select(Asset).where(Asset.canonical_code.in_(currency_codes))
            )
        }
        currency_names = {
            "USD": "United States Dollar",
            "VND": "Vietnamese Dong",
        }
        for code in sorted(currency_codes):
            if code not in assets:
                assets[code] = Asset(
                    canonical_code=code,
                    name=currency_names.get(code, code),
                    asset_type="fiat",
                    source="system",
                )
                session.add(assets[code])
        return assets

    @staticmethod
    def _recalculate_active_state(session: Session) -> None:
        active_instruments = select(UniverseMembership.instrument_id).distinct()
        session.execute(
            update(Instrument)
            .where(Instrument.instrument_type == "common_stock")
            .values(is_active=Instrument.id.in_(active_instruments))
        )
        active_companies = select(Instrument.company_id).where(
            Instrument.instrument_type == "common_stock",
            Instrument.is_active.is_(True),
        )
        session.execute(
            update(Company).values(is_active=Company.id.in_(active_companies))
        )
        active_equity_assets = select(Instrument.base_asset_id).where(
            Instrument.instrument_type == "common_stock",
            Instrument.is_active.is_(True),
        )
        session.execute(
            update(Asset)
            .where(Asset.asset_type == "equity")
            .values(is_active=Asset.id.in_(active_equity_assets))
        )

    @staticmethod
    def _lock_universes(
        session: Session,
        snapshots: tuple[UniverseSyncSnapshot, ...],
    ) -> None:
        if session.bind is None or session.bind.dialect.name != "postgresql":
            return
        lock_keys = {
            "universe-sync:VN-family"
            if snapshot.listing_country_code == "VN"
            else f"universe-sync:{snapshot.code}"
            for snapshot in snapshots
        }
        for lock_key in sorted(lock_keys):
            session.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
                {"lock_key": lock_key},
            )


def member_name(company: Company, instrument: Instrument) -> str:
    if instrument.share_class:
        return f"{company.display_name} {instrument.share_class}"
    return company.display_name


def _prefer_company_name(current: str, candidate: str) -> str:
    """Keep an issuer name when another Universe supplies a share-class label."""
    current_has_class = "class " in current.lower()
    candidate_has_class = "class " in candidate.lower()
    if current_has_class and not candidate_has_class:
        return candidate
    if not current_has_class and candidate_has_class:
        return current
    return candidate or current
