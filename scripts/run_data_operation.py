"""Execute one metadata-planned Data Operation by exact instrument ID."""
from __future__ import annotations

import argparse
import time

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
        vn_provider = (
            VnstockDataFundamentalProvider()
            if dataset == "fundamentals" and group.adapter == "vnstock_data"
            else None
        )
        for instrument_id in group.instrument_ids:
            try:
                if dataset == "prices":
                    detail = refresh_instrument(
                        instrument_id,
                        mode,
                        engine=engine,
                        emit_progress=False,
                    )
                else:
                    detail = refresh_instrument_fundamentals(
                        instrument_id,
                        mode,
                        engine=engine,
                        vn_provider=vn_provider,
                    )
            except Exception as exc:
                detail = f"failed instrument={instrument_id}: {exc}"
                errors.append(detail)
            completed += 1
            print(
                f"DATA_OPERATION: {completed}/{total} adapter={group.adapter} {detail}",
                flush=True,
            )
            delay = _adapter_delay(dataset, group.adapter)
            if completed < total and delay:
                time.sleep(delay)
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


def _adapter_delay(dataset: str, adapter: str) -> float:
    if adapter == "vnstock_data":
        return 4.1
    if dataset == "fundamentals" and adapter == "yfinance":
        return 0.25
    return 0


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
