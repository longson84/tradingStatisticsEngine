from __future__ import annotations

from datetime import date
import sys

import pytest

from scripts import run_data_operation


def test_paid_rate_limiter_spaces_starts_by_request_cost():
    now = [10.0]
    sleeps: list[float] = []

    def sleep(delay: float) -> None:
        sleeps.append(delay)
        now[0] += delay

    limiter = run_data_operation.StartRateLimiter(
        300,
        clock=lambda: now[0],
        sleeper=sleep,
    )

    limiter.wait()
    limiter.wait(2)
    limiter.wait()

    assert sleeps == pytest.approx([0.2, 0.4])


def test_paid_group_uses_bounded_workers_and_returns_every_result(monkeypatch):
    monkeypatch.setenv("VNSTOCK_REQUESTS_PER_MINUTE", "60000")
    monkeypatch.setenv("VNSTOCK_MAX_WORKERS", "2")
    calls: list[int] = []

    def execute(instrument_id, dataset, mode, engine):
        calls.append(instrument_id)
        return instrument_id, f"updated {instrument_id}", False

    monkeypatch.setattr(run_data_operation, "_execute_instrument", execute)

    results = list(run_data_operation._execute_group(
        "vnstock",
        (1, 2, 3),
        "prices",
        "incremental",
        object(),
    ))

    assert sorted(calls) == [1, 2, 3]
    assert sorted(row[0] for row in results) == [1, 2, 3]


def test_vnstock_fundamentals_reserve_all_seven_sdk_requests(monkeypatch):
    monkeypatch.setenv("VNSTOCK_REQUESTS_PER_MINUTE", "60000")
    monkeypatch.setenv("VNSTOCK_MAX_WORKERS", "1")
    costs: list[int] = []

    class Limiter:
        def __init__(self, requests_per_minute):
            pass

        def wait(self, request_cost=1):
            costs.append(request_cost)

    monkeypatch.setattr(run_data_operation, "StartRateLimiter", Limiter)
    monkeypatch.setattr(run_data_operation, "fundamental_request_cost", lambda: 7)
    monkeypatch.setattr(
        run_data_operation,
        "_execute_instrument",
        lambda instrument_id, dataset, mode, engine: (instrument_id, "ok", False),
    )

    list(run_data_operation._execute_group(
        "vnstock", (1,), "fundamentals", "incremental", object()
    ))

    assert costs == [7]


def test_vnstock_foreign_flow_reserves_one_sdk_request(monkeypatch):
    monkeypatch.setenv("VNSTOCK_REQUESTS_PER_MINUTE", "60000")
    costs: list[int] = []

    class Limiter:
        def __init__(self, requests_per_minute):
            pass

        def wait(self, request_cost=1):
            costs.append(request_cost)

    monkeypatch.setattr(run_data_operation, "StartRateLimiter", Limiter)
    monkeypatch.setattr(
        run_data_operation,
        "_execute_instrument",
        lambda instrument_id, dataset, mode, engine: (instrument_id, "ok", False),
    )
    list(run_data_operation._execute_group(
        "vnstock", (1,), "foreign_flow", "incremental", object()
    ))
    assert costs == [1]


def test_execute_instrument_dispatches_foreign_flow(monkeypatch):
    calls = []
    monkeypatch.setattr(
        run_data_operation,
        "refresh_instrument_flow",
        lambda instrument_id, mode, *, participant_type, engine: calls.append(
            (instrument_id, mode, participant_type, engine)
        ) or "flow ok",
        raising=False,
    )
    engine = object()
    result = run_data_operation._execute_instrument(7, "foreign_flow", "full", engine)
    assert result == (7, "flow ok", False)
    assert calls == [(7, "full", "foreign", engine)]


def test_execute_instrument_dispatches_proprietary_flow_participant(monkeypatch):
    calls = []
    monkeypatch.setattr(
        run_data_operation,
        "refresh_instrument_flow",
        lambda instrument_id, mode, *, participant_type, engine: calls.append(
            (instrument_id, mode, participant_type, engine)
        ) or "flow ok",
    )
    engine = object()

    result = run_data_operation._execute_instrument(
        7, "proprietary_flow", "incremental", engine
    )

    assert result == (7, "flow ok", False)
    assert calls == [(7, "incremental", "proprietary", engine)]


def test_execute_instrument_dispatches_session_stats_exact_period(monkeypatch):
    calls = []
    monkeypatch.setattr(
        run_data_operation,
        "refresh_instrument_session_statistics",
        lambda instrument_id, start, end, *, engine: calls.append(
            (instrument_id, start, end, engine)
        ) or "stats ok",
        raising=False,
    )
    engine = object()
    result = run_data_operation._execute_instrument(
        7, "session_stats", "full", engine,
        period_start=date(2026, 10, 15), period_end=date(2026, 10, 16),
    )

    assert result == (7, "stats ok", False)
    assert calls == [(7, date(2026, 10, 15), date(2026, 10, 16), engine)]


@pytest.mark.parametrize(
    ("dataset", "mode", "start", "end"),
    [
        ("session_stats", "incremental", date(2026, 10, 15), date(2026, 10, 16)),
        ("session_stats", "full", date(2026, 10, 17), date(2026, 10, 16)),
        ("trade_history", "full", date(2026, 10, 17), date(2026, 10, 16)),
        ("trade_history", "incremental", None, date(2026, 10, 16)),
        ("trade_history", "incremental", date(2026, 10, 15), None),
    ],
)
def test_exact_period_cli_rejects_invalid_period_before_database_work(
    monkeypatch, dataset, mode, start, end,
):
    monkeypatch.setattr(
        run_data_operation,
        "create_db_engine",
        lambda *args, **kwargs: pytest.fail("database should not be opened"),
    )

    with pytest.raises(ValueError):
        run_data_operation.run_data_operation(
            "instrument", "7", dataset, mode,
            period_start=start, period_end=end,
        )


def test_trade_history_parser_accepts_and_passes_exact_period(monkeypatch):
    calls = []
    monkeypatch.setattr(sys, "argv", [
        "run_data_operation", "--scope-type", "instrument", "--scope-id", "7",
        "--dataset", "trade_history", "--mode", "full",
        "--period-start", "2026-10-15", "--period-end", "2026-10-16",
    ])
    monkeypatch.setattr(
        run_data_operation, "run_data_operation",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    run_data_operation.main()
    assert calls == [(("instrument", "7", "trade_history", "full"), {
        "database_url": None, "period_start": date(2026, 10, 15),
        "period_end": date(2026, 10, 16),
    })]


def test_trade_history_paid_group_uses_shared_limiter_and_dispatches_exact_dates(monkeypatch):
    monkeypatch.setenv("VNSTOCK_REQUESTS_PER_MINUTE", "300")
    monkeypatch.setenv("VNSTOCK_MAX_WORKERS", "1")
    reservations, calls = [], []
    engine = object()
    original_wait = run_data_operation.StartRateLimiter.wait

    def reserve(limiter, request_cost=1):
        reservations.append(request_cost)
        return original_wait(limiter, request_cost)

    def refresh(instrument_id, start, end, *, mode, engine):
        calls.append((instrument_id, start, end, mode, engine))
        return "trade history ok"

    monkeypatch.setattr(run_data_operation.StartRateLimiter, "wait", reserve)
    monkeypatch.setattr(run_data_operation, "refresh_instrument_trade_statistics", refresh, raising=False)
    results = list(run_data_operation._execute_group(
        "vnstock", (7,), "trade_history", "full", engine,
        period_start=date(2026, 10, 15), period_end=date(2026, 10, 16),
    ))
    assert results == [(7, "trade history ok", False)]
    assert reservations == [1]
    assert calls == [(
        7, date(2026, 10, 15), date(2026, 10, 16), "full", engine,
    )]


def test_trade_history_paid_instrument_retries_one_failed_attempt_safely(monkeypatch):
    attempts = []

    class Limiter:
        def wait(self, request_cost=1):
            attempts.append(request_cost)

    results = iter([
        (7, "failed instrument=7: temporary provider error", True),
        (7, "trade history ok", False),
    ])
    monkeypatch.setattr(
        run_data_operation, "_dispatch_instrument", lambda *args: next(results)
    )
    monkeypatch.setattr(run_data_operation.time, "sleep", lambda delay: None)

    result = run_data_operation._execute_paid_instrument(
        Limiter(), 1, 7, "trade_history", "incremental", object(),
        date(2026, 10, 15), date(2026, 10, 16),
    )

    assert result == (7, "trade history ok", False)
    assert attempts == [1, 1]


@pytest.mark.parametrize("dataset", ["foreign_flow", "proprietary_flow"])
def test_participant_flow_paid_instrument_retries_once_and_reserves_each_attempt(
    dataset, monkeypatch,
):
    reservations = []

    class Limiter:
        def wait(self, request_cost=1):
            reservations.append(request_cost)

    results = iter([
        (7, "failed instrument=7: temporary provider error", True),
        (7, "flow ok", False),
    ])
    monkeypatch.delenv("VNSTOCK_FLOW_MAX_ATTEMPTS", raising=False)
    monkeypatch.setattr(
        run_data_operation, "_dispatch_instrument", lambda *args: next(results)
    )
    monkeypatch.setattr(run_data_operation.time, "sleep", lambda delay: None)

    result = run_data_operation._execute_paid_instrument(
        Limiter(), 1, 7, dataset, "incremental", object(),
    )

    assert result == (7, "flow ok", False)
    assert reservations == [1, 1]


@pytest.mark.parametrize("dataset", ["foreign_flow", "proprietary_flow"])
def test_participant_flow_paid_instrument_returns_final_failure_after_hard_cap(
    dataset, monkeypatch,
):
    reservations = []

    class Limiter:
        def wait(self, request_cost=1):
            reservations.append(request_cost)

    failure = (7, "failed instrument=7: provider unavailable", True)
    monkeypatch.setenv("VNSTOCK_FLOW_MAX_ATTEMPTS", "99")
    monkeypatch.setattr(
        run_data_operation, "_dispatch_instrument", lambda *args: failure
    )
    monkeypatch.setattr(run_data_operation.time, "sleep", lambda delay: None)

    result = run_data_operation._execute_paid_instrument(
        Limiter(), 1, 7, dataset, "full", object(),
    )

    assert result == failure
    assert reservations == [1, 1, 1]


@pytest.mark.parametrize("mode,start,end", [
    ("incremental", None, date(2026, 10, 16)),
    ("full", date(2026, 10, 15), None),
    ("incremental", date(2026, 10, 17), date(2026, 10, 16)),
])
def test_trade_history_dispatch_rejects_invalid_period_before_refresh(monkeypatch, mode, start, end):
    monkeypatch.setattr(
        run_data_operation, "refresh_instrument_trade_statistics",
        lambda *args, **kwargs: pytest.fail("invalid requests must not refresh"),
        raising=False,
    )
    instrument_id, detail, failed = run_data_operation._execute_instrument(
        7, "trade_history", mode, object(), period_start=start, period_end=end,
    )
    assert (instrument_id, failed) == (7, True)
    assert "requires" in detail or "on or before" in detail


def test_invalid_paid_limits_fall_back_to_silver_defaults(monkeypatch):
    monkeypatch.setenv("VNSTOCK_REQUESTS_PER_MINUTE", "invalid")
    monkeypatch.setenv("VNSTOCK_MAX_WORKERS", "0")

    assert run_data_operation._positive_env_int(
        "VNSTOCK_REQUESTS_PER_MINUTE", 300
    ) == 300
    assert run_data_operation._positive_env_int(
        "VNSTOCK_MAX_WORKERS", 5
    ) == 5
