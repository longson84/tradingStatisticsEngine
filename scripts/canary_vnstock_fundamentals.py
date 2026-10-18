"""Validate one acquisition-dated Gen 5 fundamental snapshot before writing."""
from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta

import pandas as pd
from sqlalchemy.orm import Session

from api.db.session import create_db_engine
from api.fundamental_provider import fetch_provider_fundamentals
from api.repositories.sqlalchemy_fundamental_repository import (
    SqlAlchemyFundamentalRepository,
)
from api.repositories.sqlalchemy_instrument_routing_repository import (
    SqlAlchemyInstrumentRoutingRepository,
)
from api.services.fundamental_write_service import FundamentalWriteService


def snapshot_errors(
    fetched: pd.DataFrame,
    *,
    observed_at: datetime,
) -> list[str]:
    if len(fetched) != 1:
        return [f"expected one current snapshot, received {len(fetched)}"]
    effective_date = pd.to_datetime(
        fetched.iloc[0].get("effective_date"), errors="coerce"
    )
    if pd.isna(effective_date):
        return ["effective_date is missing"]
    observed_utc = (
        observed_at.replace(tzinfo=UTC)
        if observed_at.tzinfo is None
        else observed_at.astimezone(UTC)
    )
    expected = observed_utc.date() + timedelta(days=1)
    if effective_date.date() != expected:
        return ["effective_date is not the day after acquisition"]
    return []


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="FPT")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    symbol = args.symbol.upper().strip()
    observed_at = datetime.now(UTC)
    fetched, source, methodology = fetch_provider_fundamentals(symbol, "vnstock")
    errors = snapshot_errors(fetched, observed_at=observed_at)
    if errors:
        raise RuntimeError("Gen 5 fundamentals canary failed: " + "; ".join(errors))
    row = fetched.iloc[0]
    print(
        f"{symbol}: period={row['period']} effective={row['effective_date'].date()} "
        f"source={source}",
        flush=True,
    )
    if not args.write:
        return
    engine = create_db_engine()
    with Session(engine) as session:
        metadata = SqlAlchemyInstrumentRoutingRepository(
            session
        ).find_instrument_route_metadata("listing", symbol)
        if metadata is None:
            raise RuntimeError(f"Unknown PostgreSQL instrument: {symbol}")
        instrument_id = metadata.instrument_id
    with Session(engine) as session, session.begin():
        result = FundamentalWriteService(
            SqlAlchemyFundamentalRepository(session)
        ).store_provider_frame(
            instrument_id=instrument_id,
            source=source,
            methodology=methodology,
            fetched_at=observed_at,
            frame=fetched,
        )
    print(
        f"{symbol}: wrote reports={result.report_count} facts={result.fact_count} "
        f"valuations={result.valuation_count}",
        flush=True,
    )


if __name__ == "__main__":
    main()
