"""Execute one metadata-planned Data Operation by exact instrument ID."""
from __future__ import annotations

import argparse
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from datetime import date
import os
from threading import Lock
import time
from typing import Callable

from sqlalchemy.orm import Session

from api.db.session import create_db_engine
from api.providers.vietnam_fundamentals import (
    VnstockFundamentalProvider,
    fundamental_request_cost,
)
from api.repositories.sqlalchemy_data_operation_repository import (
    SqlAlchemyDataOperationRepository,
)
from api.repositories.sqlalchemy_instrument_routing_repository import (
    SqlAlchemyInstrumentRoutingRepository,
)
from api.services.data_operation_service import DataOperationService
from api.schemas.data_operations import is_exact_period_dataset
from scripts.refresh_instrument_fundamentals import (
    refresh_instrument_fundamentals,
)
from scripts.refresh_instrument_history import refresh_instrument
from scripts.refresh_instrument_flow import refresh_instrument_flow
from scripts.refresh_instrument_session_statistics import (
    refresh_instrument_session_statistics,
)
from scripts.refresh_instrument_trade_statistics import (
    refresh_instrument_trade_statistics,
)


def run_data_operation(
    scope_type: str,
    scope_id: str,
    dataset: str,
    mode: str,
    *,
    database_url: str | None = None,
    period_start: date | None = None,
    period_end: date | None = None,
) -> None:
    _validate_exact_period(dataset, mode, period_start, period_end)
    engine = create_db_engine(database_url)
    with Session(engine) as session:
        plan = DataOperationService(
            SqlAlchemyDataOperationRepository(session),
            SqlAlchemyInstrumentRoutingRepository(session),
        ).plan(scope_type, scope_id, dataset)
    if not plan.can_run:
        raise RuntimeError(plan.message)

    total = plan.eligible_count
    completed = 0
    errors: list[str] = []
    for group in plan.groups:
        for instrument_id, detail, error in _execute_group(
            group.adapter,
            group.instrument_ids,
            dataset,
            mode,
            engine,
            period_start=period_start,
            period_end=period_end,
        ):
            if error:
                errors.append(detail)
            completed += 1
            print(
                f"DATA_OPERATION: {completed}/{total} adapter={group.adapter} {detail}",
                flush=True,
            )
    if errors:
        raise RuntimeError(
            f"{len(errors)}/{total} instrument updates failed: "
            + "; ".join(errors[:10])
        )
    print(
        f"DATA_OPERATION_COMPLETE: updated {total} instruments across "
        f"{len(plan.groups)} adapters",
        flush=True,
    )


def _execute_group(
    adapter: str,
    instrument_ids: tuple[int, ...],
    dataset: str,
    mode: str,
    engine,
    *,
    period_start: date | None = None,
    period_end: date | None = None,
):
    if adapter != "vnstock":
        for index, instrument_id in enumerate(instrument_ids):
            yield _dispatch_instrument(
                instrument_id, dataset, mode, engine, period_start, period_end
            )
            if (
                dataset == "fundamentals"
                and adapter == "yfinance"
                and index + 1 < len(instrument_ids)
            ):
                time.sleep(0.25)
        return

    requests_per_minute = _positive_env_int(
        "VNSTOCK_REQUESTS_PER_MINUTE", 300
    )
    workers = min(
        len(instrument_ids),
        _positive_env_int("VNSTOCK_MAX_WORKERS", 5),
    )
    limiter = StartRateLimiter(requests_per_minute)
    request_cost = fundamental_request_cost() if dataset == "fundamentals" else 1
    with ThreadPoolExecutor(
        max_workers=workers,
        thread_name_prefix="vnstock-data",
    ) as executor:
        futures: dict[Future, int] = {
            executor.submit(
                _execute_paid_instrument,
                limiter,
                request_cost,
                instrument_id,
                dataset,
                mode,
                engine,
                period_start,
                period_end,
            ): instrument_id
            for instrument_id in instrument_ids
        }
        for future in as_completed(futures):
            yield future.result()


def _execute_paid_instrument(
    limiter: "StartRateLimiter",
    request_cost: int,
    instrument_id: int,
    dataset: str,
    mode: str,
    engine,
    period_start: date | None = None,
    period_end: date | None = None,
):
    max_attempts = (
        min(_positive_env_int("VNSTOCK_TRADE_HISTORY_MAX_ATTEMPTS", 2), 3)
        if dataset == "trade_history" else 1
    )
    for attempt in range(1, max_attempts + 1):
        limiter.wait(request_cost)
        result = _dispatch_instrument(
            instrument_id, dataset, mode, engine, period_start, period_end
        )
        if not result[2] or attempt == max_attempts:
            return result
        time.sleep(0.5 * attempt)
    raise AssertionError("unreachable")


def _dispatch_instrument(
    instrument_id: int,
    dataset: str,
    mode: str,
    engine,
    period_start: date | None,
    period_end: date | None,
):
    if is_exact_period_dataset(dataset):
        return _execute_instrument(
            instrument_id, dataset, mode, engine,
            period_start=period_start, period_end=period_end,
        )
    return _execute_instrument(instrument_id, dataset, mode, engine)


def _execute_instrument(
    instrument_id: int,
    dataset: str,
    mode: str,
    engine,
    *,
    period_start: date | None = None,
    period_end: date | None = None,
) -> tuple[int, str, bool]:
    try:
        _validate_exact_period(dataset, mode, period_start, period_end)
        if dataset == "prices":
            detail = refresh_instrument(
                instrument_id,
                mode,
                engine=engine,
                emit_progress=False,
            )
        elif dataset == "fundamentals":
            provider = (
                VnstockFundamentalProvider()
                if dataset == "fundamentals"
                else None
            )
            detail = refresh_instrument_fundamentals(
                instrument_id,
                mode,
                engine=engine,
                vn_provider=provider,
            )
        elif dataset == "foreign_flow":
            detail = refresh_instrument_flow(
                instrument_id, mode, participant_type="foreign", engine=engine
            )
        elif dataset == "proprietary_flow":
            detail = refresh_instrument_flow(
                instrument_id, mode, participant_type="proprietary", engine=engine
            )
        elif is_exact_period_dataset(dataset):
            refresh = (
                refresh_instrument_trade_statistics
                if dataset == "trade_history"
                else refresh_instrument_session_statistics
            )
            detail = refresh(
                instrument_id, period_start, period_end, engine=engine,
                **({"mode": mode} if dataset == "trade_history" else {}),
            )
        else:
            raise ValueError(f"Unsupported dataset: {dataset}")
    except Exception as exc:
        return instrument_id, f"failed instrument={instrument_id}: {exc}", True
    return instrument_id, detail, False


def _validate_exact_period(
    dataset: str,
    mode: str,
    period_start: date | None,
    period_end: date | None,
) -> None:
    if not is_exact_period_dataset(dataset):
        return
    if period_start is None or period_end is None:
        raise ValueError(f"{dataset} requires period_start and period_end")
    if dataset == "session_stats" and mode != "full":
        raise ValueError(f"{dataset} requires full mode")
    if period_start > period_end:
        raise ValueError("period_start must be on or before period_end")


class StartRateLimiter:
    """Space task starts at a shared paid-subscription request budget."""

    def __init__(
        self,
        requests_per_minute: int,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if requests_per_minute <= 0:
            raise ValueError("requests_per_minute must be positive")
        self._interval = 60.0 / requests_per_minute
        self._clock = clock
        self._sleeper = sleeper
        self._next_start = 0.0
        self._lock = Lock()

    def wait(self, request_cost: int = 1) -> None:
        if request_cost <= 0:
            raise ValueError("request_cost must be positive")
        with self._lock:
            now = self._clock()
            scheduled = max(now, self._next_start)
            self._next_start = scheduled + self._interval * request_cost
        delay = scheduled - now
        if delay > 0:
            self._sleeper(delay)


def _positive_env_int(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scope-type", choices=("category", "universe", "watchlist", "instrument"), required=True
    )
    parser.add_argument("--scope-id", required=True)
    parser.add_argument(
        "--dataset",
        choices=(
            "prices", "fundamentals", "foreign_flow", "proprietary_flow",
            "session_stats", "trade_history",
        ),
        required=True,
    )
    parser.add_argument("--mode", choices=("incremental", "full"), required=True)
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--period-start", type=date.fromisoformat, default=None)
    parser.add_argument("--period-end", type=date.fromisoformat, default=None)
    args = parser.parse_args()
    run_data_operation(
        args.scope_type,
        args.scope_id,
        args.dataset,
        args.mode,
        database_url=args.database_url,
        period_start=args.period_start,
        period_end=args.period_end,
    )


if __name__ == "__main__":
    main()
