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
    monkeypatch.setenv("VNSTOCK_DATA_REQUESTS_PER_MINUTE", "60000")
    monkeypatch.setenv("VNSTOCK_DATA_MAX_WORKERS", "2")
    calls: list[int] = []

    def execute(instrument_id, dataset, mode, engine):
        calls.append(instrument_id)
        return instrument_id, f"updated {instrument_id}", False

    monkeypatch.setattr(run_data_operation, "_execute_instrument", execute)

    results = list(run_data_operation._execute_group(
        "vnstock_data",
        (1, 2, 3),
        "prices",
        "incremental",
        object(),
    ))

    assert sorted(calls) == [1, 2, 3]
    assert sorted(row[0] for row in results) == [1, 2, 3]


def test_invalid_paid_limits_fall_back_to_silver_defaults(monkeypatch):
    monkeypatch.setenv("VNSTOCK_DATA_REQUESTS_PER_MINUTE", "invalid")
    monkeypatch.setenv("VNSTOCK_DATA_MAX_WORKERS", "0")

    assert run_data_operation._positive_env_int(
        "VNSTOCK_DATA_REQUESTS_PER_MINUTE", 300
    ) == 300
    assert run_data_operation._positive_env_int(
        "VNSTOCK_DATA_MAX_WORKERS", 5
    ) == 5
