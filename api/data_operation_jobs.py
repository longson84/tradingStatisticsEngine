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

from api.market_data_config import PROJECT_ROOT
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
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        values = asdict(self)
        values.pop("adapter_keys")
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
    )
    key = (scope_type, scope_id, dataset)
    acquired: list[str] = []
    try:
        if dataset == "prices":
            for adapter in job.adapter_keys:
                acquire_price_refresh(
                    adapter,
                    job.id,
                    f"{scope_type} {scope_name}",
                )
                acquired.append(adapter)
        with _lock:
            if key in _active_keys:
                raise RuntimeError(
                    f"This {scope_type} already has an active {dataset} update"
                )
            _jobs[job.id] = job
            _active_keys[key] = job.id
        Thread(target=_run_job, args=(job.id,), daemon=True).start()
    except Exception:
        with _lock:
            _jobs.pop(job.id, None)
            _active_keys.pop(key, None)
        for adapter in acquired:
            release_price_refresh(adapter, job.id)
        raise
    return job


def get_job(job_id: str) -> DataOperationJob | None:
    with _lock:
        return _jobs.get(job_id)


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


def _run_job(job_id: str) -> None:
    with _lock:
        job = _jobs[job_id]
        job.status = "running"
        job.started_at = _now()
        job.message = "Starting data update"
        scope_type = job.scope_type
        scope_id = job.scope_id
        dataset = job.dataset
        mode = job.mode
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
                if match:
                    current.current = int(match.group(1))
                    current.total = int(match.group(2))
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
    else:
        with _lock:
            current = _jobs[job_id]
            current.status = "completed"
            current.finished_at = _now()
            current.current = current.total
            current.message = lines[-1] if lines else "Data update completed"
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
