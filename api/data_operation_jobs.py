"""Unified in-process registry for Data Operations background jobs."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import re
import subprocess
import sys
from threading import Lock, Thread
from typing import Literal
from uuid import uuid4

from api.market_data_config import PROJECT_ROOT
from api.universe_refresh_jobs import (
    UniverseRefreshJob,
    get_job as get_universe_job,
    start_refresh_job as start_universe_refresh,
)
from api.watchlist_refresh_jobs import (
    WatchlistRefreshJob,
    get_job as get_watchlist_job,
    start_refresh_job as start_watchlist_refresh,
)


ScopeType = Literal["universe", "watchlist", "instrument"]
Dataset = Literal["prices", "fundamentals"]
Mode = Literal["incremental", "full"]
Status = Literal["queued", "running", "completed", "failed"]
BackendKind = Literal["universe", "watchlist", "instrument"]
_PROGRESS = re.compile(r"INSTRUMENT\s+\d+:\s+(\d+)/(\d+)")


@dataclass
class DataOperationJob:
    id: str
    scope_type: ScopeType
    scope_id: str
    scope_name: str
    dataset: Dataset
    mode: Mode
    status: Status = "queued"
    current: int = 0
    total: int = 0
    message: str = "Waiting to start"
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None
    backend_kind: BackendKind = "instrument"

    def to_dict(self) -> dict:
        values = asdict(self)
        values.pop("backend_kind")
        return values


_jobs: dict[str, DataOperationJob] = {}
_active_keys: dict[tuple[ScopeType, str, Dataset], str] = {}
_lock = Lock()


def start_universe_operation(
    code: str,
    name: str,
    dataset: Dataset,
    mode: Mode,
    routing_adapter: str,
) -> DataOperationJob:
    backend = start_universe_refresh(
        code, mode, dataset, routing_adapter=routing_adapter
    )
    return _register_backend(
        backend.id, "universe", code, name, dataset, mode, "universe"
    )


def start_watchlist_operation(
    watchlist_id: int, name: str, routing_adapter: str, mode: Mode
) -> DataOperationJob:
    if mode != "incremental":
        raise RuntimeError("Watchlist refresh currently supports incremental mode only")
    backend = start_watchlist_refresh(watchlist_id, name, routing_adapter)
    return _register_backend(
        backend.id,
        "watchlist",
        str(watchlist_id),
        name,
        "prices",
        mode,
        "watchlist",
    )


def start_instrument_operation(
    instrument_id: int, name: str, mode: Mode
) -> DataOperationJob:
    job = DataOperationJob(
        id=uuid4().hex,
        scope_type="instrument",
        scope_id=str(instrument_id),
        scope_name=name,
        dataset="prices",
        mode=mode,
    )
    key = (job.scope_type, job.scope_id, job.dataset)
    with _lock:
        if key in _active_keys:
            raise RuntimeError("This instrument already has an active price update")
        _jobs[job.id] = job
        _active_keys[key] = job.id
    Thread(target=_run_instrument_job, args=(job.id,), daemon=True).start()
    return job


def get_job(job_id: str) -> DataOperationJob | None:
    with _lock:
        job = _jobs.get(job_id)
    if job is None:
        return None
    if job.backend_kind == "universe":
        backend = get_universe_job(job.id)
        if backend is not None:
            _sync_universe(job, backend)
    elif job.backend_kind == "watchlist":
        backend = get_watchlist_job(job.id)
        if backend is not None:
            _sync_watchlist(job, backend)
    return job


def _register_backend(
    job_id: str,
    scope_type: ScopeType,
    scope_id: str,
    scope_name: str,
    dataset: Dataset,
    mode: Mode,
    backend_kind: BackendKind,
) -> DataOperationJob:
    job = DataOperationJob(
        id=job_id,
        scope_type=scope_type,
        scope_id=scope_id,
        scope_name=scope_name,
        dataset=dataset,
        mode=mode,
        backend_kind=backend_kind,
    )
    with _lock:
        _jobs[job.id] = job
    return get_job(job.id) or job


def _sync_universe(job: DataOperationJob, backend: UniverseRefreshJob) -> None:
    with _lock:
        job.status = backend.status
        job.current = backend.current
        job.total = backend.total
        job.message = backend.message
        job.started_at = backend.started_at
        job.finished_at = backend.finished_at
        job.error = backend.error


def _sync_watchlist(job: DataOperationJob, backend: WatchlistRefreshJob) -> None:
    with _lock:
        job.status = backend.status
        job.current = backend.current
        job.total = backend.total
        job.message = backend.message
        job.started_at = backend.started_at
        job.finished_at = backend.finished_at
        job.error = backend.error


def _run_instrument_job(job_id: str) -> None:
    with _lock:
        job = _jobs[job_id]
        job.status = "running"
        job.started_at = _now()
        job.message = "Starting instrument price update"
        instrument_id = job.scope_id
        mode = job.mode
    command = [
        sys.executable,
        "-u",
        "-m",
        "scripts.refresh_instrument_history",
        "--instrument-id",
        instrument_id,
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
                if match:
                    current.current = int(match.group(1))
                    current.total = int(match.group(2))
        return_code = process.wait()
        if return_code != 0:
            raise RuntimeError(
                "\n".join(lines[-8:]) or f"Refresh exited with code {return_code}"
            )
    except Exception as exc:
        with _lock:
            current = _jobs[job_id]
            current.status = "failed"
            current.finished_at = _now()
            current.error = str(exc)
            current.message = "Price update failed; existing rows were retained"
    else:
        with _lock:
            current = _jobs[job_id]
            current.status = "completed"
            current.finished_at = _now()
            current.current = current.total or 1
            current.total = current.total or 1
            current.message = lines[-1] if lines else "Price update completed"
    finally:
        with _lock:
            current = _jobs[job_id]
            _active_keys.pop(
                (current.scope_type, current.scope_id, current.dataset), None
            )


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()
