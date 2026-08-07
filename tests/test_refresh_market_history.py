"""Tests for cross-universe reuse in the market-history refresh script."""
from __future__ import annotations

from datetime import date
import sys

import pandas as pd

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


class FakeQuote:
    responses: dict[tuple[str, str], pd.DataFrame | Exception] = {}
    calls: list[tuple[str, str]] = []

    def __init__(self, symbol: str, source: str):
        self.symbol = symbol
        self.source = source

    def history(self, **kwargs):
        self.calls.append((self.symbol, self.source))
        response = self.responses[(self.symbol, self.source)]
        if isinstance(response, Exception):
            raise response
        return response.copy()


def test_us2000_snapshot_contains_official_listed_equity_holdings():
    symbols = refresh_market_history._symbols("US2000")

    assert len(symbols) == 1954
    assert "MOG-A" in symbols
    assert "CRD-A" in symbols


def test_vnall_snapshot_is_exact_union_of_vn_size_segments():
    vn30 = set(refresh_market_history._symbols("VN30"))
    vnmid = set(refresh_market_history._symbols("VNMID"))
    vnsml = set(refresh_market_history._symbols("VNSML"))

    assert len(vn30) == 30
    assert len(vnmid) == 70
    assert len(vnsml) == 215
    assert not vn30 & vnmid
    assert not (vn30 | vnmid) & vnsml
    assert set(refresh_market_history._symbols("VN100")) == vn30 | vnmid
    assert set(refresh_market_history._symbols("VNALL")) == vn30 | vnmid | vnsml


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


def test_vn_fetch_uses_current_kbs_without_fallback():
    FakeQuote.calls = []
    FakeQuote.responses = {
        ("FPT", "KBS"): _provider_rows(["2026-08-07"], [100.0]),
    }

    result = refresh_market_history._fetch_vn_history(
        FakeQuote,
        "FPT",
        date(2026, 8, 1),
        date(2026, 8, 7),
        fallback_delay=0,
    )

    assert FakeQuote.calls == [("FPT", "KBS")]
    assert result.outcome == "current"
    assert result.selected_source == "vnstock-kbs"
    assert result.returned_through == date(2026, 8, 7)


def test_vn_fetch_falls_back_when_kbs_is_behind_and_selects_newer_vci():
    FakeQuote.calls = []
    FakeQuote.responses = {
        ("FPT", "KBS"): _provider_rows(["2026-08-06"], [99.0]),
        ("FPT", "VCI"): _provider_rows(["2026-08-07"], [100.0]),
    }

    result = refresh_market_history._fetch_vn_history(
        FakeQuote,
        "FPT",
        date(2026, 8, 1),
        date(2026, 8, 7),
        fallback_delay=0,
    )

    assert FakeQuote.calls == [("FPT", "KBS"), ("FPT", "VCI")]
    assert result.outcome == "current"
    assert result.selected_source == "vnstock-vci"
    assert result.returned_through == date(2026, 8, 7)


def test_vn_fetch_records_checked_no_new_bar_when_both_sources_are_behind():
    FakeQuote.calls = []
    FakeQuote.responses = {
        ("HTV", "KBS"): _provider_rows(["2026-08-03"], [15.25]),
        ("HTV", "VCI"): _provider_rows(["2026-08-03"], [15.25]),
    }

    result = refresh_market_history._fetch_vn_history(
        FakeQuote,
        "HTV",
        date(2026, 8, 1),
        date(2026, 8, 7),
        fallback_delay=0,
    )

    assert result.outcome == "checked_no_new_bar"
    assert result.returned_through == date(2026, 8, 3)
    assert "provider overlap=1 mismatched=0" in result.detail


def test_vn_fetch_records_failure_when_both_sources_fail():
    FakeQuote.calls = []
    FakeQuote.responses = {
        ("BAD", "KBS"): RuntimeError("kbs unavailable"),
        ("BAD", "VCI"): RuntimeError("vci unavailable"),
    }

    result = refresh_market_history._fetch_vn_history(
        FakeQuote,
        "BAD",
        date(2026, 8, 1),
        date(2026, 8, 7),
        fallback_delay=0,
    )

    assert result.outcome == "failed"
    assert result.selected_source is None
    assert "KBS: RuntimeError" in result.detail
    assert "VCI: RuntimeError" in result.detail


def test_all_refresh_runs_overlap_sources_in_reuse_order(monkeypatch):
    engine = object()
    calls: list[tuple] = []
    completed_vn_session = date(2026, 8, 4)

    monkeypatch.setattr(
        refresh_market_history, "create_db_engine", lambda database_url: engine
    )
    monkeypatch.setattr(
        refresh_market_history,
        "latest_completed_session",
        lambda now, market: completed_vn_session,
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
        ["refresh_market_history", "--market", "all", "--mode", "incremental"],
    )

    refresh_market_history.main()

    assert calls == [
        ("benchmark", "SPX", "incremental"),
        ("US2000", "incremental", None),
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
