from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from api.db.models import (
    Base,
    Company,
    Instrument,
    InstrumentSymbol,
    PriceBar,
    Universe,
    UniverseMembership,
    UniverseSyncRun,
    Watchlist,
    WatchlistMembership,
)
from api.providers.universe import (
    UniverseProviderRegistry,
    UniverseSnapshot,
    make_constituent,
    make_identifier,
)
from api.providers.nasdaq_symbol_directory import (
    USListingVenue,
    USListingVenueCatalog,
)
from api.providers.universe_venues import resolve_snapshot_venues
from api.repositories.sqlalchemy_universe_sync_repository import (
    SqlAlchemyUniverseSyncRepository,
)
from api.repositories.universe_sync_repository import UniverseSyncRejectedError
from api.services.universe_sync_service import (
    VN_UNIVERSE_FAMILY,
    UniverseSyncService,
)
from scripts.sync_equity_universes import build_parser, selected_universes


class MutableUS30Provider:
    supported_universes = frozenset({"US30"})

    def __init__(self) -> None:
        self.tickers = [f"T{index:03d}" for index in range(30)]
        self.error: Exception | None = None
        self.sector: str | None = "Industrials"

    def fetch(self, universe: str) -> UniverseSnapshot:
        if self.error is not None:
            raise self.error
        shared_identifier = make_identifier("sec_cik", "12345")
        return UniverseSnapshot(
            code="US30",
            name="Test Dow 30",
            country_code="US",
            description="Test current constituents",
            effective_date=date(2026, 8, 13),
            fetched_at=datetime(2026, 8, 13, tzinfo=UTC),
            source="test-live-provider",
            constituents=tuple(
                make_constituent(
                    symbol=ticker,
                    country_code="US",
                    company_name=(
                        "Same Provider Name" if index in (2, 3)
                        else f"Company {ticker}"
                    ),
                    sector=self.sector,
                    exchange="NASDAQ",
                    company_identifiers=(shared_identifier,)
                    if index < 2 and shared_identifier is not None
                    else (),
                )
                for index, ticker in enumerate(self.tickers)
            ),
        )


@pytest.fixture
def sync_setup():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    provider = MutableUS30Provider()
    repository = SqlAlchemyUniverseSyncRepository(engine)
    service = UniverseSyncService(
        repository,
        UniverseProviderRegistry((provider,)),
        us_listing_catalog_fetcher=lambda: pytest.fail(
            "venue catalog should not be fetched for resolved exchanges"
        ),
    )
    return engine, provider, service


def test_live_sync_is_idempotent_and_reconciles_companies_by_identifier(sync_setup):
    engine, _provider, service = sync_setup

    first = service.synchronize(("US30",))
    second = service.synchronize(("US30",))

    assert first[0].added_count == 30
    assert second[0].added_count == 0
    assert second[0].unchanged_count == 30
    with Session(engine) as session:
        first_instrument = session.scalar(
            select(Instrument).where(Instrument.symbol == "T000")
        )
        second_instrument = session.scalar(
            select(Instrument).where(Instrument.symbol == "T001")
        )
        assert first_instrument is not None and second_instrument is not None
        assert first_instrument.company_id == second_instrument.company_id
        same_name = session.scalars(
            select(Instrument)
            .where(Instrument.symbol.in_(("T002", "T003")))
            .order_by(Instrument.symbol)
        ).all()
        assert len(same_name) == 2
        assert same_name[0].company_id != same_name[1].company_id
        assert first_instrument.base_asset is not None
        assert first_instrument.quote_asset is not None
        assert first_instrument.venue is not None
        assert {row.namespace for row in first_instrument.symbols} == {
            "canonical", "listing", "test-live-provider",
        }
        assert session.scalar(select(func.count(UniverseSyncRun.id))) == 2


def test_sync_does_not_erase_non_null_company_metadata(sync_setup):
    engine, provider, service = sync_setup
    service.synchronize(("US30",))
    provider.sector = None

    service.synchronize(("US30",))

    with Session(engine) as session:
        company = session.scalar(
            select(Company)
            .join(Instrument)
            .where(Instrument.symbol == "T010")
        )
        assert company is not None and company.sector == "Industrials"


def test_membership_replacement_preserves_observations_and_watchlists(sync_setup):
    engine, provider, service = sync_setup
    service.synchronize(("US30",))
    with Session(engine) as session, session.begin():
        removed = session.scalar(
            select(Instrument).where(Instrument.symbol == "T000")
        )
        assert removed is not None
        watchlist = Watchlist(name="Keep", name_key="keep", description="")
        session.add(watchlist)
        session.flush()
        session.add_all([
            PriceBar(
                instrument_id=removed.id,
                trading_date=date(2026, 8, 12),
                open=10,
                high=11,
                low=9,
                close=10,
                volume=100,
                currency="USD",
                price_scale=1,
                price_basis="provider_unspecified",
                source="test",
                fetched_at=datetime(2026, 8, 13, tzinfo=UTC),
            ),
            WatchlistMembership(
                watchlist_id=watchlist.id,
                instrument_id=removed.id,
                position=0,
            ),
        ])
        removed_id = removed.id

    provider.tickers = [f"T{index:03d}" for index in range(1, 31)]
    result = service.synchronize(("US30",))[0]

    assert (result.added_count, result.removed_count) == (1, 1)
    with Session(engine) as session:
        removed = session.get(Instrument, removed_id)
        assert removed is not None and removed.is_active is False
        assert session.scalar(
            select(func.count(PriceBar.id)).where(PriceBar.instrument_id == removed_id)
        ) == 1
        assert session.scalar(
            select(func.count(WatchlistMembership.id)).where(
                WatchlistMembership.instrument_id == removed_id
            )
        ) == 1
        assert session.scalar(
            select(func.count(UniverseMembership.id))
            .join(Universe)
            .where(Universe.code == "US30")
        ) == 30


def test_failed_provider_and_rejected_large_change_keep_last_known_membership(sync_setup):
    engine, provider, service = sync_setup
    service.synchronize(("US30",))
    provider.error = RuntimeError("provider offline")

    with pytest.raises(RuntimeError, match="provider offline"):
        service.synchronize(("US30",))

    provider.error = None
    provider.tickers = [f"X{index:03d}" for index in range(30)]
    with pytest.raises(UniverseSyncRejectedError, match="--force"):
        service.synchronize(("US30",))

    with Session(engine) as session:
        tickers = set(session.scalars(
            select(InstrumentSymbol.symbol)
            .join(Instrument, Instrument.id == InstrumentSymbol.instrument_id)
            .join(
                UniverseMembership,
                UniverseMembership.instrument_id == Instrument.id,
            )
            .join(Universe, Universe.id == UniverseMembership.universe_id)
            .where(
                Universe.code == "US30",
                InstrumentSymbol.namespace == "canonical",
                InstrumentSymbol.valid_to.is_(None),
                InstrumentSymbol.is_primary.is_(True),
            )
        ))
        assert tickers == {f"T{index:03d}" for index in range(30)}
        statuses = list(session.scalars(
            select(UniverseSyncRun.status).order_by(UniverseSyncRun.id)
        ))
        assert statuses == ["succeeded", "failed", "failed"]

    forced = service.synchronize(("US30",), force=True)[0]
    assert (forced.added_count, forced.removed_count) == (30, 30)


def test_dry_run_reports_diff_without_writing(sync_setup):
    engine, _provider, service = sync_setup

    result = service.synchronize(("US30",), dry_run=True)[0]

    assert result.dry_run is True
    assert result.added_count == 30
    with Session(engine) as session:
        assert session.scalar(select(func.count(Universe.id))) == 0
        assert session.scalar(select(func.count(UniverseSyncRun.id))) == 0


def test_sync_audit_retains_latest_100_attempts_per_universe(sync_setup):
    engine, _provider, service = sync_setup
    service.synchronize(("US30",))
    with Session(engine) as session, session.begin():
        for index in range(100):
            timestamp = datetime(2026, 8, 14, tzinfo=UTC) + timedelta(seconds=index)
            session.add(UniverseSyncRun(
                universe_code="US30",
                source="seed",
                status="failed",
                started_at=timestamp,
                finished_at=timestamp,
                received_count=0,
                added_count=0,
                removed_count=0,
                unchanged_count=0,
                error=f"failure {index}",
            ))

    service._repository.record_failures(  # type: ignore[attr-defined]
        universe_codes=("US30",),
        source="latest",
        started_at=datetime(2026, 8, 15, tzinfo=UTC),
        error="latest failure",
    )

    with Session(engine) as session:
        rows = session.scalars(
            select(UniverseSyncRun)
            .where(UniverseSyncRun.universe_code == "US30")
            .order_by(UniverseSyncRun.started_at.desc(), UniverseSyncRun.id.desc())
        ).all()
        assert len(rows) == 100
        assert rows[0].error == "latest failure"
        assert all(row.error != "failure 0" for row in rows)


def test_vietnam_selection_expands_to_the_atomic_family(sync_setup):
    _engine, _provider, service = sync_setup
    service._providers._providers.update({  # type: ignore[attr-defined]
        code: object() for code in VN_UNIVERSE_FAMILY
    })

    assert service.expand_universe_codes(("VN30",)) == VN_UNIVERSE_FAMILY


def test_sync_cli_selection_controls():
    parser = build_parser()

    assert selected_universes(parser.parse_args(["--country", "us"])) == (
        "US500", "US30", "US100", "US2000",
    )
    assert selected_universes(
        parser.parse_args(["--universe", "US500", "--universe", "US30"])
    ) == ("US500", "US30")


def test_missing_us_exchange_is_resolved_from_nasdaq_trader_catalog():
    snapshot = UniverseSnapshot(
        code="US500",
        name="S&P 500",
        country_code="US",
        description="",
        effective_date=None,
        fetched_at=datetime(2026, 8, 13, tzinfo=UTC),
        source="test",
        constituents=(
            make_constituent(
                symbol="BRK.B",
                country_code="US",
                company_name="Berkshire Hathaway",
            ),
        ),
    )
    catalog = USListingVenueCatalog(
        listings=(USListingVenue(
            primary_symbols=("BRK.B",),
            alternate_symbols=("BRK-B",),
            venue_code="NYSE",
        ),),
        fetched_at=datetime(2026, 8, 13, tzinfo=UTC),
    )

    resolved = resolve_snapshot_venues(snapshot, us_catalog=catalog)

    assert resolved.constituents[0].canonical_symbol == "BRK-B"
    assert resolved.constituents[0].listing_symbol == "BRK.B"
    assert resolved.constituents[0].exchange == "NYSE"
