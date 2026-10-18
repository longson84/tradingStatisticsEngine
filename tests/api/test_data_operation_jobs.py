from datetime import date

from sqlalchemy import create_engine
import pytest

from api import data_operation_jobs as jobs
from api.data_operation_jobs import DataOperationJob, _insert_job, _load_job
from api.db.models import Base


def test_session_stats_job_period_round_trips_through_durable_run():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    job = DataOperationJob(
        id="job1", scope_type="instrument", scope_id="42", scope_name="FPT",
        dataset="session_stats", mode="full", adapter_keys=("vnstock",), total=1,
        period_start=date(2026, 10, 15), period_end=date(2026, 10, 16),
    )

    _insert_job(engine, job)
    loaded = _load_job(engine, "job1")

    assert loaded is not None
    assert loaded.period_start == date(2026, 10, 15)
    assert loaded.period_end == date(2026, 10, 16)
    assert loaded.to_dict()["period_start"] == date(2026, 10, 15)


def test_trade_history_job_period_survives_queue_load_history_and_subprocess(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    monkeypatch.setattr(jobs, "_jobs", {})
    monkeypatch.setattr(jobs, "_active_keys", {})
    leases = []
    releases = []
    monkeypatch.setattr(jobs, "acquire_price_refresh", lambda *args: leases.append(args))
    monkeypatch.setattr(jobs, "release_price_refresh", lambda *args: releases.append(args))

    class DeferredThread:
        def __init__(self, **kwargs):
            pass

        def start(self):
            pass

    monkeypatch.setattr(jobs, "Thread", DeferredThread)
    request = dict(scope_type="instrument", scope_id="42", scope_name="FPT",
                   dataset="trade_history", mode="full", adapter_keys=("vnstock",),
                   total=1, engine=engine, period_start=date(2026, 10, 15),
                   period_end=date(2026, 10, 16))
    queued = jobs.start_data_operation_job(**request)
    assert queued.status == "queued"
    assert jobs.get_active_scope_job("instrument", "42").id == queued.id
    assert jobs.get_active_data_operation_job("instrument", "42", "trade_history").id == queued.id
    loaded = jobs._load_job(engine, queued.id)
    history, = jobs.list_jobs(engine)
    for record in (queued, loaded, history):
        assert record.dataset == "trade_history"
        assert record.period_start == date(2026, 10, 15)
        assert record.period_end == date(2026, 10, 16)
    with pytest.raises(RuntimeError, match="active trade_history"):
        jobs.start_data_operation_job(**(request | {"period_start": date(2026, 10, 14)}))
    # A rejected duplicate must retain the first run's active identity.
    assert jobs.get_active_data_operation_job("instrument", "42", "trade_history").id == queued.id
    commands = []

    class SuccessfulProcess:
        stdout = ["DATA_OPERATION: 1/1 updated instrument=42\n"]

        def wait(self):
            return 0

    def popen(command, **kwargs):
        commands.append(command)
        return SuccessfulProcess()

    monkeypatch.setattr(jobs.subprocess, "Popen", popen)
    jobs._run_job(queued.id, engine)
    assert commands[0][3:] == [
        "scripts.run_data_operation", "--scope-type", "instrument", "--scope-id", "42",
        "--dataset", "trade_history", "--mode", "full", "--period-start", "2026-10-15",
        "--period-end", "2026-10-16",
    ]
    assert leases == [("vnstock", queued.id, "instrument FPT")]
    assert releases == [("vnstock", queued.id)]
    completed, = jobs.list_jobs(engine)
    assert completed.status == "completed"
    assert completed.period_start == date(2026, 10, 15)
    assert completed.period_end == date(2026, 10, 16)
    assert jobs.get_active_scope_job("instrument", "42") is None
