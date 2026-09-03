"""In-process runner for metadata-planned Data Operations jobs."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import re
import subprocess
import sys
from threading import Lock, Thread
from typing import Literal
from uuid import uuid4

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from api.db.models import DataOperationRun
from api.project_paths import PROJECT_ROOT
from api.price_refresh_coordination import (
    acquire_price_refresh,
    release_price_refresh,
)


ScopeType = Literal["universe", "watchlist", "instrument"]
Dataset = Literal["prices", "fundamentals"]
Mode = Literal["incremental", "full"]
Status = Literal["queued", "running", "completed", "failed"]
_PROGRESS = re.compile(r"DATA_OPERATION:\s+(\d+)/(\d+)")


@dataclass
class DataOperationJob:
    id: str
    scope_type: ScopeType
    scope_id: str
    scope_name: str
    dataset: Dataset
    mode: Mode
    adapter_keys: tuple[str, ...]
    status: Status = "queued"
    current: int = 0
    total: int = 0
    message: str = "Waiting to start"
    output: tuple[str, ...] = ()
    created_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None
    succeeded: int = 0
    failed: int = 0

    def to_dict(self) -> dict:
        values = asdict(self)
        return values


_jobs: dict[str, DataOperationJob] = {}
_active_keys: dict[tuple[ScopeType, str, Dataset], str] = {}
_lock = Lock()


def start_data_operation_job(
    *,
    scope_type: ScopeType,
    scope_id: str,
    scope_name: str,
    dataset: Dataset,
    mode: Mode,
    adapter_keys: tuple[str, ...],
    total: int,
    engine: Engine,
) -> DataOperationJob:
    job = DataOperationJob(
        id=uuid4().hex,
        scope_type=scope_type,
        scope_id=scope_id,
        scope_name=scope_name,
        dataset=dataset,
        mode=mode,
        adapter_keys=tuple(sorted(set(adapter_keys))),
        total=total,
        created_at=_now(),
    )
    key = (scope_type, scope_id, dataset)
    acquired: list[str] = []
    try:
        with _lock:
            if key in _active_keys:
                raise RuntimeError(
                    f"This {scope_type} already has an active {dataset} update"
                )
            _active_keys[key] = job.id
        if dataset == "prices":
            for adapter in job.adapter_keys:
                acquire_price_refresh(
                    adapter,
                    job.id,
                    f"{scope_type} {scope_name}",
                )
                acquired.append(adapter)
        _insert_job(engine, job)
        with _lock:
            _jobs[job.id] = job
        Thread(target=_run_job, args=(job.id, engine), daemon=True).start()
    except Exception:
        with _lock:
            _jobs.pop(job.id, None)
            _active_keys.pop(key, None)
        for adapter in acquired:
            release_price_refresh(adapter, job.id)
        raise
    return job


def get_job(job_id: str, engine: Engine) -> DataOperationJob | None:
    with _lock:
        active = _jobs.get(job_id)
    return active or _load_job(engine, job_id)


def list_jobs(engine: Engine, *, limit: int = 50) -> tuple[DataOperationJob, ...]:
    with Session(engine) as session:
        rows = session.scalars(
            select(DataOperationRun)
            .order_by(DataOperationRun.created_at.desc())
            .limit(limit)
        ).all()
    return tuple(_from_row(row) for row in rows)


def get_active_scope_job(
    scope_type: ScopeType,
    scope_id: str,
) -> DataOperationJob | None:
    with _lock:
        for dataset in ("prices", "fundamentals"):
            job_id = _active_keys.get((scope_type, scope_id, dataset))
            if job_id is not None:
                return _jobs.get(job_id)
    return None


def _run_job(job_id: str, engine: Engine) -> None:
    with _lock:
        job = _jobs[job_id]
        job.status = "running"
        job.started_at = _now()
        job.message = "Starting data update"
        scope_type = job.scope_type
        scope_id = job.scope_id
        dataset = job.dataset
        mode = job.mode
        snapshot = DataOperationJob(**asdict(job))
    _update_job(engine, snapshot)
    command = [
        sys.executable,
        "-u",
        "-m",
        "scripts.run_data_operation",
        "--scope-type",
        scope_type,
        "--scope-id",
        scope_id,
        "--dataset",
        dataset,
        "--mode",
        mode,
    ]
    lines: list[str] = []
    try:
        process = subprocess.Popen(
            command,
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None
        for raw_line in process.stdout:
            line = raw_line.strip()
            if not line:
                continue
            lines = (lines + [line])[-20:]
            match = _PROGRESS.search(line)
            with _lock:
                current = _jobs[job_id]
                current.message = line
                current.output = tuple(lines)
                if match:
                    current.current = int(match.group(1))
                    current.total = int(match.group(2))
                    if " failed instrument=" in f" {line}":
                        current.failed += 1
                    else:
                        current.succeeded += 1
                snapshot = DataOperationJob(**asdict(current))
            _update_job(engine, snapshot)
        return_code = process.wait()
        if return_code != 0:
            raise RuntimeError(
                "\n".join(lines[-8:]) or f"Update exited with code {return_code}"
            )
    except Exception as exc:
        with _lock:
            current = _jobs[job_id]
            current.status = "failed"
            current.finished_at = _now()
            current.error = str(exc)
            current.message = "Data update failed; existing observations were retained"
            current.output = tuple(lines)
            snapshot = DataOperationJob(**asdict(current))
        _update_job(engine, snapshot)
    else:
        with _lock:
            current = _jobs[job_id]
            current.status = "completed"
            current.finished_at = _now()
            current.current = current.total
            current.message = lines[-1] if lines else "Data update completed"
            current.output = tuple(lines)
            snapshot = DataOperationJob(**asdict(current))
        _update_job(engine, snapshot)
    finally:
        with _lock:
            current = _jobs[job_id]
            _active_keys.pop(
                (current.scope_type, current.scope_id, current.dataset), None
            )
        if job.dataset == "prices":
            for adapter in job.adapter_keys:
                release_price_refresh(adapter, job.id)


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _insert_job(engine: Engine, job: DataOperationJob) -> None:
    with Session(engine) as session, session.begin():
        session.add(DataOperationRun(
            id=job.id,
            scope_type=job.scope_type,
            scope_id=job.scope_id,
            scope_name=job.scope_name,
            dataset=job.dataset,
            mode=job.mode,
            adapter_keys=list(job.adapter_keys),
            status=job.status,
            current=job.current,
            total=job.total,
            succeeded=job.succeeded,
            failed=job.failed,
            message=job.message,
            output=list(job.output),
            created_at=_parse_time(job.created_at),
            started_at=_parse_time(job.started_at),
            finished_at=_parse_time(job.finished_at),
            error=job.error,
        ))


def _update_job(engine: Engine, job: DataOperationJob) -> None:
    with Session(engine) as session, session.begin():
        row = session.get(DataOperationRun, job.id)
        if row is None:
            return
        row.status = job.status
        row.current = job.current
        row.total = job.total
        row.succeeded = job.succeeded
        row.failed = job.failed
        row.message = job.message
        row.output = list(job.output)
        row.started_at = _parse_time(job.started_at)
        row.finished_at = _parse_time(job.finished_at)
        row.error = job.error


def _load_job(engine: Engine, job_id: str) -> DataOperationJob | None:
    with Session(engine) as session:
        row = session.get(DataOperationRun, job_id)
        return _from_row(row) if row is not None else None


def _from_row(row: DataOperationRun) -> DataOperationJob:
    return DataOperationJob(
        id=row.id,
        scope_type=row.scope_type,  # type: ignore[arg-type]
        scope_id=row.scope_id,
        scope_name=row.scope_name,
        dataset=row.dataset,  # type: ignore[arg-type]
        mode=row.mode,  # type: ignore[arg-type]
        adapter_keys=tuple(row.adapter_keys),
        status=row.status,  # type: ignore[arg-type]
        current=row.current,
        total=row.total,
        succeeded=row.succeeded,
        failed=row.failed,
        message=row.message,
        output=tuple(row.output),
        created_at=_format_time(row.created_at),
        started_at=_format_time(row.started_at),
        finished_at=_format_time(row.finished_at),
        error=row.error,
    )


def _parse_time(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _format_time(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).replace(microsecond=0).isoformat()
