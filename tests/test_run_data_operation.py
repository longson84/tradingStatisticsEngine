from __future__ import annotations

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
        lambda instrument_id, mode, *, engine: calls.append((instrument_id, mode, engine)) or "flow ok",
        raising=False,
    )
    engine = object()
    result = run_data_operation._execute_instrument(7, "foreign_flow", "full", engine)
    assert result == (7, "flow ok", False)
    assert calls == [(7, "full", engine)]


def test_invalid_paid_limits_fall_back_to_silver_defaults(monkeypatch):
    monkeypatch.setenv("VNSTOCK_REQUESTS_PER_MINUTE", "invalid")
    monkeypatch.setenv("VNSTOCK_MAX_WORKERS", "0")

    assert run_data_operation._positive_env_int(
        "VNSTOCK_REQUESTS_PER_MINUTE", 300
    ) == 300
    assert run_data_operation._positive_env_int(
        "VNSTOCK_MAX_WORKERS", 5
    ) == 5
