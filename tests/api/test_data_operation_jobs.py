from datetime import date

from sqlalchemy import create_engine

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
