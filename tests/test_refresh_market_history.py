"""Tests for cross-universe reuse in the market-history refresh script."""
from __future__ import annotations

from datetime import date
import sys
from types import SimpleNamespace

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from api.db.models import Base, Company, Instrument, Universe, UniverseMembership
from api.providers.vietnam_market import (
    VietnamProviderMetadata,
    VietnamProviderResult,
)
from scripts import refresh_market_history


def _rows(symbol: str, dates: list[str], closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame({
        "symbol": symbol,
        "date": pd.to_datetime(dates),
        "open": closes,
        "high": closes,
        "low": closes,
        "close": closes,
        "volume": 1_000.0,
    })


def _provider_rows(dates: list[str], closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame({
        "time": pd.to_datetime(dates),
        "open": closes,
        "high": closes,
        "low": closes,
        "close": closes,
        "volume": 1_000.0,
    })


class FakeProvider:
    def __init__(
        self,
        package: str,
        source: str,
        responses: dict[str, pd.DataFrame | Exception],
        calls: list[tuple[str, str]],
    ):
        self.package = package
        self.source = source
        self.access_mode = "sponsored" if package == "vnstock_data" else "community"
        self.responses = responses
        self.calls = calls

    def ohlcv(self, symbol, start, end, *, interval="1D"):
        self.calls.append((symbol, self.source))
        response = self.responses[symbol]
        if isinstance(response, Exception):
            raise response
        return VietnamProviderResult(
            frame=response.copy(),
            metadata=VietnamProviderMetadata(
                package=self.package,
                package_version="3.2.7" if self.package == "vnstock_data" else "4.0.5",
                access_mode=self.access_mode,
                upstream_source=self.source,
                method="ohlcv",
                symbol=symbol,
                requested_start=start,
                requested_end=end,
            ),
        )

    def trade_history(self, symbol, start, end):
        raise AssertionError("not used")


def test_symbols_resolve_only_active_canonical_database_members():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session, session.begin():
        issuer = Company(display_name="Issuer", country_code="US", source="test")
        active = Instrument(
            company=issuer, ticker="ACTIVE", currency="USD", source="test"
        )
        inactive = Instrument(
            company=issuer, ticker="INACTIVE", currency="USD", source="test",
            is_active=False,
        )
        universe = Universe(code="TEST", name="Test", source="test")
        session.add_all((
            UniverseMembership(universe=universe, instrument=active, source="test"),
            UniverseMembership(universe=universe, instrument=inactive, source="test"),
        ))

    assert refresh_market_history._symbols("TEST", engine) == ["ACTIVE"]


def test_us_download_plan_skips_current_symbols_and_only_fetches_stale_delta():
    existing = pd.concat([
        _rows("CURRENT", ["2021-01-04", "2026-08-03"], [10.0, 20.0]),
        _rows("STALE", ["2021-01-04", "2026-07-24"], [10.0, 20.0]),
    ])

    plan = refresh_market_history._market_download_plan(
        existing,
        ["CURRENT", "STALE", "MISSING"],
        date(2021, 1, 1),
        date(2026, 8, 3),
        "incremental",
    )

    assert "CURRENT" not in {symbol for group in plan.values() for symbol in group}
    assert plan[date(2026, 7, 17)] == ["STALE"]
    assert plan[date(2021, 1, 1)] == ["MISSING"]


def test_us_download_plan_treats_weekend_cache_as_current():
    existing = _rows("AAA", ["2021-01-04", "2026-07-31"], [10.0, 20.0])

    plan = refresh_market_history._market_download_plan(
        existing,
        ["AAA"],
        date(2021, 1, 1),
        date(2026, 8, 2),
        "incremental",
    )

    assert plan == {}


def test_full_download_plan_can_trust_cache_rebuilt_earlier_in_same_run():
    existing = _rows("OVERLAP", ["2006-12-13", "2026-07-31"], [10.0, 20.0])

    plan = refresh_market_history._market_download_plan(
        existing,
        ["OVERLAP", "NEW"],
        date(1900, 1, 1),
        date(2026, 8, 1),
        "full",
        assume_existing_complete=True,
    )

    assert plan == {date(1900, 1, 1): ["NEW"]}


def test_vn_fetch_uses_current_sponsor_without_fallback():
    calls: list[tuple[str, str]] = []
    sponsor = FakeProvider(
        "vnstock_data",
        "VCI",
        {"FPT": _provider_rows(["2026-08-07"], [100.0])},
        calls,
    )

    result = refresh_market_history._fetch_vn_history(
        sponsor,
        "FPT",
        date(2026, 8, 1),
        date(2026, 8, 7),
        fallback_delay=0,
    )

    assert calls == [("FPT", "VCI")]
    assert result.outcome == "current"
    assert result.selected_source == "vnstock-data-3.2.7-vci"
    assert result.returned_through == date(2026, 8, 7)


def test_vn_fetch_uses_explicit_community_fallback_when_sponsor_is_behind():
    calls: list[tuple[str, str]] = []
    sponsor = FakeProvider(
        "vnstock_data",
        "VCI",
        {"FPT": _provider_rows(["2026-08-06"], [99.0])},
        calls,
    )
    community = FakeProvider(
        "vnstock",
        "KBS",
        {"FPT": _provider_rows(["2026-08-07"], [100.0])},
        calls,
    )

    result = refresh_market_history._fetch_vn_history(
        sponsor,
        "FPT",
        date(2026, 8, 1),
        date(2026, 8, 7),
        community_fallbacks=(community,),
        fallback_delay=0,
    )

    assert calls == [("FPT", "VCI"), ("FPT", "KBS")]
    assert result.outcome == "current"
    assert result.selected_source == "vnstock-4.0.5-kbs"
    assert result.returned_through == date(2026, 8, 7)


def test_vn_fetch_records_checked_no_new_bar_when_all_sources_are_behind():
    calls: list[tuple[str, str]] = []
    sponsor = FakeProvider(
        "vnstock_data",
        "VCI",
        {"HTV": _provider_rows(["2026-08-03"], [15.25])},
        calls,
    )
    community = FakeProvider(
        "vnstock",
        "VCI",
        {"HTV": _provider_rows(["2026-08-03"], [15.25])},
        calls,
    )

    result = refresh_market_history._fetch_vn_history(
        sponsor,
        "HTV",
        date(2026, 8, 1),
        date(2026, 8, 7),
        community_fallbacks=(community,),
        fallback_delay=0,
    )

    assert result.outcome == "checked_no_new_bar"
    assert result.returned_through == date(2026, 8, 3)
    assert "provider overlap=1 mismatched=0" in result.detail


def test_vn_fetch_records_failure_when_sponsor_and_fallback_fail():
    calls: list[tuple[str, str]] = []
    sponsor = FakeProvider(
        "vnstock_data", "VCI", {"BAD": RuntimeError("sponsor unavailable")}, calls
    )
    community = FakeProvider(
        "vnstock", "VCI", {"BAD": RuntimeError("vci unavailable")}, calls
    )

    result = refresh_market_history._fetch_vn_history(
        sponsor,
        "BAD",
        date(2026, 8, 1),
        date(2026, 8, 7),
        community_fallbacks=(community,),
        fallback_delay=0,
    )

    assert result.outcome == "failed"
    assert result.selected_source is None
    assert "vnstock-data-3.2.7-vci: RuntimeError" in result.detail
    assert "vnstock-4.0.5-vci: RuntimeError" in result.detail


def test_vn30_benchmark_legacy_cache_is_revalidated_with_sponsored_vci(
    monkeypatch,
):
    existing = _rows(
        "VN30",
        ["2026-08-06", "2026-08-07"],
        [1_850.0, 1_860.0],
    )
    calls: list[tuple[str, str]] = []
    sponsor = FakeProvider(
        "vnstock_data",
        "VCI",
        {"VN30": _provider_rows(
            ["2026-08-06", "2026-08-07"],
            [1_850.0, 1_860.0],
        )},
        calls,
    )
    saved: dict[str, object] = {}
    monkeypatch.setattr(
        refresh_market_history, "_existing_benchmark", lambda benchmark: existing
    )
    monkeypatch.setattr(
        refresh_market_history,
        "_existing_benchmark_manifest",
        lambda benchmark: {"source": "vnstock-vci"},
    )
    monkeypatch.setattr(
        refresh_market_history,
        "save_benchmark_history",
        lambda benchmark, data, manifest: saved.update({
            "benchmark": benchmark,
            "data": data,
            "manifest": manifest,
        }),
    )

    refresh_market_history.refresh_benchmark(
        "VN30",
        date(2000, 1, 1),
        date(2026, 8, 7),
        "incremental",
        vn_provider=sponsor,
    )

    assert calls == [("VN30", "VCI")]
    assert saved["benchmark"] == "VN30"
    assert len(saved["data"]) == 2
    assert saved["manifest"]["source"] == "vnstock-data-3.2.7-vci"


def test_vn30_benchmark_parity_blocks_changed_history():
    existing = _rows("VN30", ["2026-08-07"], [1_860.0])
    changed = _rows("VN30", ["2026-08-07"], [1_861.0])

    with pytest.raises(RuntimeError, match="mismatched_rows=1"):
        refresh_market_history._assert_benchmark_parity(existing, changed)


def test_all_refresh_runs_overlap_sources_in_reuse_order(monkeypatch):
    engine = object()
    calls: list[tuple] = []
    completed_vn_session = date(2026, 8, 4)

    monkeypatch.setattr(
        refresh_market_history, "create_db_engine", lambda database_url: engine
    )
    monkeypatch.setattr(
        refresh_market_history,
        "latest_completed_venue_session",
        lambda now, schedule: completed_vn_session,
    )
    monkeypatch.setattr(
        refresh_market_history,
        "_scope_instruments",
        lambda received_engine, universe: universe,
    )
    monkeypatch.setattr(
        refresh_market_history,
        "_refresh_targets",
        lambda received_engine, universe: (
            [SimpleNamespace(
                price_adapter=(
                    "vnstock_data" if universe.startswith("VN") else "yfinance"
                )
            )],
            {1: SimpleNamespace(
                price_adapter=(
                    "vnstock_data" if universe.startswith("VN") else "yfinance"
                ),
                schedule=object(),
                full_history_start=date(2000, 1, 1),
            )},
        ),
    )
    monkeypatch.setattr(
        refresh_market_history,
        "refresh_benchmark",
        lambda benchmark, start, end, mode: calls.append(
            ("benchmark", benchmark, mode)
        ),
    )

    def refresh_us(received_engine, universe, start, end, mode, **kwargs):
        assert received_engine is engine
        already_refreshed = kwargs.get("already_refreshed")
        calls.append((
            universe,
            mode,
            set(already_refreshed) if already_refreshed is not None else None,
        ))
        return {
            "US2000": {"RUT_ONLY", "OVERLAP"},
            "US500": {"SP500_ONLY", "OVERLAP"},
            "US100": {"NASDAQ_ONLY", "OVERLAP"},
        }[universe]

    def refresh_vn(received_engine, universe, start, end, delay, mode, **kwargs):
        assert received_engine is engine
        assert end == completed_vn_session
        already_refreshed = kwargs.get("already_refreshed")
        calls.append((
            universe,
            mode,
            set(already_refreshed) if already_refreshed is not None else None,
        ))
        return {
            "VNALL": {"VN30_MEMBER", "VNMID_MEMBER", "VNSML_MEMBER"},
            "VN100": {"VN30_MEMBER", "VNMID_MEMBER"},
            "VN30": {"VN30_MEMBER"},
            "VNMID": {"VNMID_MEMBER"},
            "VNSML": {"VNSML_MEMBER"},
        }[universe]

    monkeypatch.setattr(refresh_market_history, "refresh_us_market", refresh_us)
    monkeypatch.setattr(refresh_market_history, "refresh_vn_market", refresh_vn)
    monkeypatch.setattr(
        sys,
        "argv",
        ["refresh_market_history", "--universe", "all", "--mode", "incremental"],
    )

    refresh_market_history.main()

    assert calls == [
        ("benchmark", "SPX", "incremental"),
        ("US2000", "incremental", set()),
        ("US500", "incremental", {"RUT_ONLY", "OVERLAP"}),
        (
            "US100",
            "incremental",
            {"RUT_ONLY", "SP500_ONLY", "OVERLAP"},
        ),
        ("benchmark", "VN30", "incremental"),
        ("VNALL", "incremental", set()),
        (
            "VN100",
            "incremental",
            {"VN30_MEMBER", "VNMID_MEMBER", "VNSML_MEMBER"},
        ),
        (
            "VN30",
            "incremental",
            {"VN30_MEMBER", "VNMID_MEMBER", "VNSML_MEMBER"},
        ),
        (
            "VNMID",
            "incremental",
            {"VN30_MEMBER", "VNMID_MEMBER", "VNSML_MEMBER"},
        ),
        (
            "VNSML",
            "incremental",
            {"VN30_MEMBER", "VNMID_MEMBER", "VNSML_MEMBER"},
        ),
    ]
