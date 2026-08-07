"""In-process registry for background watchlist price refresh jobs."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
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


JobStatus = Literal["queued", "running", "completed", "failed"]
_PROGRESS = re.compile(r"WATCHLIST\s+\d+:\s+(\d+)/(\d+)")


@dataclass
class WatchlistRefreshJob:
    id: str
    watchlist_id: int
    watchlist_name: str
    market: str
    status: JobStatus = "queued"
    current: int = 0
    total: int = 0
    message: str = "Waiting to start"
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


_jobs: dict[str, WatchlistRefreshJob] = {}
_active_by_watchlist: dict[int, str] = {}
_latest_by_watchlist: dict[int, str] = {}
_lock = Lock()


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def get_job(job_id: str) -> WatchlistRefreshJob | None:
    with _lock:
        return _jobs.get(job_id)


def get_active_job(watchlist_id: int) -> WatchlistRefreshJob | None:
    with _lock:
        job_id = _active_by_watchlist.get(watchlist_id)
        return _jobs.get(job_id) if job_id else None


def list_latest_jobs() -> tuple[WatchlistRefreshJob, ...]:
    with _lock:
        return tuple(
            _jobs[job_id]
            for _, job_id in sorted(_latest_by_watchlist.items())
            if job_id in _jobs
        )


def start_refresh_job(
    watchlist_id: int, watchlist_name: str, market: str
) -> WatchlistRefreshJob:
    job = WatchlistRefreshJob(
        id=uuid4().hex,
        watchlist_id=watchlist_id,
        watchlist_name=watchlist_name,
        market=market,
    )
    acquire_price_refresh(market, job.id, f"watchlist {watchlist_name}")
    try:
        with _lock:
            if watchlist_id in _active_by_watchlist:
                raise RuntimeError("This watchlist is already refreshing")
            _jobs[job.id] = job
            _active_by_watchlist[watchlist_id] = job.id
            _latest_by_watchlist[watchlist_id] = job.id
        Thread(target=_run_job, args=(job.id,), daemon=True).start()
    except Exception:
        with _lock:
            _jobs.pop(job.id, None)
            _active_by_watchlist.pop(watchlist_id, None)
            if _latest_by_watchlist.get(watchlist_id) == job.id:
                _latest_by_watchlist.pop(watchlist_id, None)
        release_price_refresh(market, job.id)
        raise
    return job


def _run_job(job_id: str) -> None:
    with _lock:
        job = _jobs[job_id]
        job.status = "running"
        job.started_at = _now()
        job.message = "Starting watchlist price refresh"
        watchlist_id = job.watchlist_id
    command = [
        sys.executable,
        "-u",
        "-m",
        "scripts.refresh_watchlist_history",
        "--watchlist-id",
        str(watchlist_id),
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
                current_job = _jobs[job_id]
                current_job.message = line
                if match:
                    current_job.current = int(match.group(1))
                    current_job.total = int(match.group(2))
        return_code = process.wait()
        if return_code != 0:
            raise RuntimeError(
                "\n".join(lines[-8:]) or f"Refresh exited with code {return_code}"
            )
    except Exception as exc:
        with _lock:
            current_job = _jobs[job_id]
            current_job.status = "failed"
            current_job.finished_at = _now()
            current_job.error = str(exc)
            current_job.message = "Refresh failed; existing prices were retained"
    else:
        with _lock:
            current_job = _jobs[job_id]
            current_job.status = "completed"
            current_job.finished_at = _now()
            provider_errors = next(
                (line for line in reversed(lines) if line.startswith("Refresh errors:")),
                None,
            )
            if provider_errors:
                current_job.message = (
                    "Refresh completed with provider errors; successful prices were stored"
                )
                current_job.error = provider_errors
            else:
                current_job.message = "Watchlist prices updated successfully"
            if current_job.total:
                current_job.current = current_job.total
    finally:
        with _lock:
            _active_by_watchlist.pop(watchlist_id, None)
        release_price_refresh(job.market, job_id)
