"""Validate sponsored VCI fundamentals against PostgreSQL before writing."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from api.db.session import create_db_engine
from api.fundamental_provider import VALUE_COLUMNS, fetch_provider_fundamentals
from api.repositories.sqlalchemy_fundamental_repository import (
    SqlAlchemyFundamentalRepository,
)
from api.repositories.sqlalchemy_instrument_routing_repository import (
    SqlAlchemyInstrumentRoutingRepository,
)
from api.services.fundamental_service import FundamentalService
from api.services.fundamental_write_service import FundamentalWriteService


def parity_errors(existing: pd.DataFrame, fetched: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    identity = ["effective_date", "period_end", "period"]
    left = existing.sort_values("effective_date").reset_index(drop=True)
    right = fetched.sort_values("effective_date").reset_index(drop=True)
    if len(left) != len(right):
        errors.append(f"snapshot count differs: stored={len(left)} fetched={len(right)}")
        return errors
    for column in identity:
        old = left[column].astype(str)
        new = right[column].astype(str)
        if not old.equals(new):
            errors.append(f"identity differs in {column}")
    # VCI can revise the newest reported period after its first publication
    # (including market-cap-based ratios). Require strict history through the
    # penultimate snapshot while allowing the normal refresh to update latest.
    value_left = left.iloc[:-1]
    value_right = right.iloc[:-1]
    for column in VALUE_COLUMNS:
        old = pd.to_numeric(value_left[column], errors="coerce").to_numpy(dtype=float)
        new = pd.to_numeric(value_right[column], errors="coerce").to_numpy(dtype=float)
        if not np.array_equal(np.isnan(old), np.isnan(new)):
            errors.append(f"null coverage differs in {column}")
            continue
        if not np.allclose(old, new, rtol=1e-8, atol=1e-6, equal_nan=True):
            errors.append(f"values differ in {column}")
    return errors


def latest_value_changes(existing: pd.DataFrame, fetched: pd.DataFrame) -> list[str]:
    if existing.empty or fetched.empty:
        return []
    old_row = existing.sort_values("effective_date").iloc[-1]
    new_row = fetched.sort_values("effective_date").iloc[-1]
    changes: list[str] = []
    for column in VALUE_COLUMNS:
        old = pd.to_numeric(pd.Series([old_row[column]]), errors="coerce").iloc[0]
        new = pd.to_numeric(pd.Series([new_row[column]]), errors="coerce").iloc[0]
        if pd.isna(old) and pd.isna(new):
            continue
        if pd.isna(old) != pd.isna(new) or not np.isclose(
            old, new, rtol=1e-8, atol=1e-6
        ):
            changes.append(column)
    return changes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="FPT")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    symbol = args.symbol.upper().strip()
    engine = create_db_engine()
    with Session(engine) as session:
        repository = SqlAlchemyFundamentalRepository(session)
        metadata = SqlAlchemyInstrumentRoutingRepository(
            session
        ).find_instrument_route_metadata("listing", symbol)
        if metadata is None:
            raise RuntimeError(f"Unknown PostgreSQL instrument: {symbol}")
        instrument_id = metadata.instrument_id
        stored = FundamentalService(repository).get_instrument_history(instrument_id)
    fetched, source, methodology = fetch_provider_fundamentals(
        symbol, "vnstock_data"
    )
    errors = parity_errors(stored.snapshots, fetched)
    print(
        f"{symbol}: stored={len(stored.snapshots)} sponsored={len(fetched)} "
        f"range={fetched.effective_date.min().date()}.."
        f"{fetched.effective_date.max().date()} source={source}",
        flush=True,
    )
    if errors:
        raise RuntimeError("Sponsored fundamentals parity failed: " + "; ".join(errors))
    print(
        f"{symbol}: strict identity and historical-value parity passed",
        flush=True,
    )
    latest_changes = latest_value_changes(stored.snapshots, fetched)
    if latest_changes:
        print(
            f"{symbol}: newest-period provider revisions: "
            + ", ".join(latest_changes),
            flush=True,
        )
    if not args.write:
        return
    with Session(engine) as session, session.begin():
        result = FundamentalWriteService(
            SqlAlchemyFundamentalRepository(session)
        ).store_provider_frame(
            instrument_id=instrument_id,
            source=source,
            methodology=methodology,
            fetched_at=datetime.now(timezone.utc),
            frame=fetched,
        )
    print(
        f"{symbol}: wrote reports={result.report_count} facts={result.fact_count} "
        f"valuations={result.valuation_count}",
        flush=True,
    )


if __name__ == "__main__":
    main()
