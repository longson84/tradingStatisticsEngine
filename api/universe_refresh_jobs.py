"""In-process registry for canonical Universe refresh jobs."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import re
import subprocess
import sys
from threading import Lock, Thread
from typing import Literal
from uuid import uuid4

from api.market_data_config import PROJECT_ROOT, SUPPORTED_UNIVERSES
from api.price_refresh_coordination import (
    acquire_price_refresh,
    release_price_refresh,
)


JobMode = Literal["incremental", "full"]
JobDataset = Literal["prices", "fundamentals"]
JobStatus = Literal["queued", "running", "completed", "failed"]
_PROGRESS = re.compile(
    r"(?:US100|US2000|US500|VNALL|VN100|VN30|VNMID|VNSML):\s+(\d+)/(\d+)"
)


@dataclass
class UniverseRefreshJob:
    id: str
    universe: str
    mode: JobMode
    dataset: JobDataset = "prices"
    routing_adapter: str = ""
    status: JobStatus = "queued"
    current: int = 0
    total: int = 0
    message: str = "Waiting to start"
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


_jobs: dict[str, UniverseRefreshJob] = {}
_active_by_universe: dict[str, str] = {}
_latest_by_universe: dict[str, str] = {}
_lock = Lock()


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def get_job(job_id: str) -> UniverseRefreshJob | None:
    with _lock:
        return _jobs.get(job_id)


def _job_key(universe: str, dataset: JobDataset) -> str:
    return f"{universe.upper()}:{dataset}"


def get_active_job(universe: str, dataset: JobDataset = "prices") -> UniverseRefreshJob | None:
    normalized = _job_key(universe, dataset)
    with _lock:
        job_id = _active_by_universe.get(normalized)
        return _jobs.get(job_id) if job_id else None


def get_latest_job(universe: str, dataset: JobDataset = "prices") -> UniverseRefreshJob | None:
    normalized = _job_key(universe, dataset)
    with _lock:
        job_id = _latest_by_universe.get(normalized)
        return _jobs.get(job_id) if job_id else None


def clear_job_history(universe: str, dataset: JobDataset = "prices") -> None:
    normalized = _job_key(universe, dataset)
    with _lock:
        job_id = _latest_by_universe.pop(normalized, None)
        if job_id:
            _jobs.pop(job_id, None)


def start_refresh_job(
    universe: str,
    mode: JobMode,
    dataset: JobDataset = "prices",
    *,
    routing_adapter: str,
) -> UniverseRefreshJob:
    normalized = universe.upper()
    if normalized not in SUPPORTED_UNIVERSES:
        raise ValueError(f"Unsupported universe: {universe!r}")
    if mode not in ("incremental", "full"):
        raise ValueError(f"Unsupported refresh mode: {mode!r}")
    if dataset not in ("prices", "fundamentals"):
        raise ValueError(f"Unsupported refresh dataset: {dataset!r}")

    key = _job_key(normalized, dataset)
    if not routing_adapter:
        raise ValueError("A resolved routing adapter is required")
    job = UniverseRefreshJob(
        id=uuid4().hex,
        universe=normalized,
        mode=mode,
        dataset=dataset,
        routing_adapter=routing_adapter,
    )
    coordination_key = routing_adapter
    if dataset == "prices":
        acquire_price_refresh(coordination_key, job.id, normalized)
    try:
        with _lock:
            if key in _active_by_universe:
                raise RuntimeError(
                    f"A {dataset} refresh for {normalized} is already running"
                )
            _jobs[job.id] = job
            _active_by_universe[key] = job.id
            _latest_by_universe[key] = job.id
        Thread(target=_run_job, args=(job.id,), daemon=True).start()
    except Exception:
        with _lock:
            _jobs.pop(job.id, None)
            _active_by_universe.pop(key, None)
            if _latest_by_universe.get(key) == job.id:
                _latest_by_universe.pop(key, None)
        if dataset == "prices":
            release_price_refresh(coordination_key, job.id)
        raise
    return job


def _run_job(job_id: str) -> None:
    with _lock:
        job = _jobs[job_id]
        job.status = "running"
        job.started_at = _now()
        job.message = "Starting refresh"
        universe = job.universe
        mode = job.mode
        dataset = job.dataset

    if dataset == "fundamentals":
        command = [
            sys.executable,
            "-u",
            "-m",
            "scripts.refresh_market_fundamentals",
            "--universe",
            universe.lower(),
            "--mode",
            mode,
            "--job-id",
            job_id,
        ]
    else:
        command = [
            sys.executable,
            "-u",
            "-m",
            "scripts.refresh_market_history",
            "--universe",
            universe.lower(),
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
            lines.append(line)
            lines = lines[-20:]
            match = _PROGRESS.search(line)
            with _lock:
                current_job = _jobs[job_id]
                current_job.message = line
                if match:
                    current_job.current = int(match.group(1))
                    current_job.total = int(match.group(2))
        return_code = process.wait()
        if return_code != 0:
            detail = "\n".join(lines[-8:]) or f"Refresh exited with code {return_code}"
            raise RuntimeError(detail)
    except Exception as exc:
        with _lock:
            current_job = _jobs[job_id]
            current_job.status = "failed"
            current_job.finished_at = _now()
            current_job.error = str(exc)
            current_job.message = "Refresh failed; the previous data was kept"
    else:
        with _lock:
            current_job = _jobs[job_id]
            current_job.status = "completed"
            current_job.finished_at = _now()
            result_line = next(
                (line for line in reversed(lines) if ": result " in line),
                None,
            )
            current_job.message = result_line or "Universe data updated successfully"
            if current_job.total:
                current_job.current = current_job.total
    finally:
        with _lock:
            _active_by_universe.pop(_job_key(universe, dataset), None)
        if dataset == "prices":
            release_price_refresh(job.routing_adapter, job_id)
