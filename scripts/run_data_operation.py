"""Execute one metadata-planned Data Operation by exact instrument ID."""
from __future__ import annotations

import argparse
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
import os
from threading import Lock
import time
from typing import Callable

from sqlalchemy.orm import Session

from api.db.session import create_db_engine
from api.providers.vietnam_fundamentals import VnstockDataFundamentalProvider
from api.repositories.sqlalchemy_data_operation_repository import (
    SqlAlchemyDataOperationRepository,
)
from api.repositories.sqlalchemy_instrument_routing_repository import (
    SqlAlchemyInstrumentRoutingRepository,
)
from api.services.data_operation_service import DataOperationService
from scripts.refresh_instrument_fundamentals import (
    refresh_instrument_fundamentals,
)
from scripts.refresh_instrument_history import refresh_instrument


def run_data_operation(
    scope_type: str,
    scope_id: str,
    dataset: str,
    mode: str,
    *,
    database_url: str | None = None,
) -> None:
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
):
    if adapter != "vnstock_data":
        for index, instrument_id in enumerate(instrument_ids):
            yield _execute_instrument(instrument_id, dataset, mode, engine)
            if (
                dataset == "fundamentals"
                and adapter == "yfinance"
                and index + 1 < len(instrument_ids)
            ):
                time.sleep(0.25)
        return

    requests_per_minute = _positive_env_int(
        "VNSTOCK_DATA_REQUESTS_PER_MINUTE", 300
    )
    workers = min(
        len(instrument_ids),
        _positive_env_int("VNSTOCK_DATA_MAX_WORKERS", 5),
    )
    limiter = StartRateLimiter(requests_per_minute)
    request_cost = 2 if dataset == "fundamentals" else 1
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
):
    limiter.wait(request_cost)
    return _execute_instrument(instrument_id, dataset, mode, engine)


def _execute_instrument(
    instrument_id: int,
    dataset: str,
    mode: str,
    engine,
) -> tuple[int, str, bool]:
    try:
        if dataset == "prices":
            detail = refresh_instrument(
                instrument_id,
                mode,
                engine=engine,
                emit_progress=False,
            )
        else:
            provider = (
                VnstockDataFundamentalProvider()
                if dataset == "fundamentals"
                else None
            )
            detail = refresh_instrument_fundamentals(
                instrument_id,
                mode,
                engine=engine,
                vn_provider=provider,
            )
    except Exception as exc:
        return instrument_id, f"failed instrument={instrument_id}: {exc}", True
    return instrument_id, detail, False


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
        "--scope-type", choices=("universe", "watchlist", "instrument"), required=True
    )
    parser.add_argument("--scope-id", required=True)
    parser.add_argument("--dataset", choices=("prices", "fundamentals"), required=True)
    parser.add_argument("--mode", choices=("incremental", "full"), required=True)
    parser.add_argument("--database-url", default=None)
    args = parser.parse_args()
    run_data_operation(
        args.scope_type,
        args.scope_id,
        args.dataset,
        args.mode,
        database_url=args.database_url,
    )


if __name__ == "__main__":
    main()
