from __future__ import annotations

from datetime import UTC, datetime, timedelta

from scripts.refresh_market_fundamentals import (
    REUSE_WINDOW,
    _recently_refreshed,
)


class StubFundamentalRepository:
    def __init__(self, fetched_at: datetime | None):
        self.fetched_at = fetched_at
        self.calls: list[int] = []

    def get_latest_fetched_at(self, instrument_id: int):
        self.calls.append(instrument_id)
        return self.fetched_at


def test_recent_refresh_reuse_uses_database_timestamp():
    started_at = datetime(2026, 8, 3, 12, tzinfo=UTC)
    repository = StubFundamentalRepository(started_at - REUSE_WINDOW)

    assert _recently_refreshed(repository, 101, started_at)
    assert repository.calls == [101]


def test_stale_or_missing_database_snapshot_is_not_reused():
    started_at = datetime(2026, 8, 3, 12, tzinfo=UTC)

    assert not _recently_refreshed(
        StubFundamentalRepository(started_at - REUSE_WINDOW - timedelta(seconds=1)),
        201,
        started_at,
    )
    assert not _recently_refreshed(
        StubFundamentalRepository(None), 201, started_at
    )


def test_full_run_only_reuses_symbol_refreshed_during_same_ordered_run():
    run_started_at = datetime(2026, 8, 3, 12, tzinfo=UTC)

    assert _recently_refreshed(
        StubFundamentalRepository(run_started_at + timedelta(seconds=1)),
        101,
        run_started_at + timedelta(minutes=1),
        refreshed_after=run_started_at,
    )
    assert not _recently_refreshed(
        StubFundamentalRepository(run_started_at - timedelta(seconds=1)),
        101,
        run_started_at + timedelta(minutes=1),
        refreshed_after=run_started_at,
    )
