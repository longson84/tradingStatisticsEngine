"""Compare sponsored OHLCV with canonical storage and optionally upsert one symbol."""
from __future__ import annotations

import argparse
from datetime import UTC, date, datetime
import json
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from api.db.session import create_db_engine
from api.market_sessions import latest_completed_venue_session
from api.venue_calendars import venue_calendar
from api.providers.vietnam_market import (
    create_vietnam_market_provider,
    normalize_ohlcv_result,
)
from api.repositories.price_bar_repository import InstrumentPriceBarQuery
from api.repositories.sqlalchemy_price_bar_repository import (
    SqlAlchemyPriceBarRepository,
)
from api.repositories.sqlalchemy_instrument_routing_repository import (
    SqlAlchemyInstrumentRoutingRepository,
)
from api.instrument_data_routing import resolve_instrument_data_route
from api.services.price_refresh_service import (
    PriceRefreshAttempt,
    PriceRefreshService,
    PriceRefreshTarget,
)


PRICE_COLUMNS = ("open", "high", "low", "close")


def compare_frames(sponsored: pd.DataFrame, stored: pd.DataFrame) -> dict[str, Any]:
    """Return strict canary checks; provider disagreement blocks automatic writes."""
    sponsor = sponsored.copy()
    existing = stored.copy()
    sponsor["date"] = pd.to_datetime(sponsor["date"]).dt.date
    if existing.empty:
        existing = pd.DataFrame(columns=["date", *PRICE_COLUMNS, "volume"])
    else:
        existing["date"] = pd.to_datetime(existing["date"]).dt.date
    sponsor_dates = set(sponsor["date"])
    stored_dates = set(existing["date"]) if not existing.empty else set()
    overlap = sponsor.merge(existing, on="date", suffixes=("_sponsor", "_stored"))

    price_mismatch = pd.Series(False, index=overlap.index)
    max_price_difference = 0.0
    for column in PRICE_COLUMNS:
        left = pd.to_numeric(overlap[f"{column}_sponsor"], errors="coerce")
        right = pd.to_numeric(overlap[f"{column}_stored"], errors="coerce")
        differences = (left - right).abs()
        if not differences.empty:
            max_price_difference = max(
                max_price_difference,
                float(differences.max(skipna=True) or 0.0),
            )
        price_mismatch |= ~np.isclose(
            left,
            right,
            rtol=1e-9,
            atol=1e-6,
            equal_nan=True,
        )

    sponsor_volume = pd.to_numeric(
        overlap.get("volume_sponsor"), errors="coerce"
    )
    stored_volume = pd.to_numeric(overlap.get("volume_stored"), errors="coerce")
    volume_mismatch = ~np.isclose(
        sponsor_volume,
        stored_volume,
        rtol=0,
        atol=0.5,
        equal_nan=True,
    )
    missing_from_provider = stored_dates - sponsor_dates
    new_provider_dates = sponsor_dates - stored_dates
    safe_to_write = bool(
        not sponsor.empty
        and (existing.empty or not overlap.empty)
        and not missing_from_provider
        and not price_mismatch.any()
        and not volume_mismatch.any()
    )
    return {
        "sponsored_rows": len(sponsor),
        "sponsored_first_date": min(sponsor_dates).isoformat(),
        "sponsored_last_date": max(sponsor_dates).isoformat(),
        "stored_rows": len(existing),
        "stored_first_date": min(stored_dates).isoformat() if stored_dates else None,
        "stored_last_date": max(stored_dates).isoformat() if stored_dates else None,
        "overlap_rows": len(overlap),
        "missing_from_provider": len(missing_from_provider),
        "new_provider_dates": len(new_provider_dates),
        "price_mismatch_rows": int(price_mismatch.sum()),
        "volume_mismatch_rows": int(volume_mismatch.sum()),
        "max_absolute_price_difference": max_price_difference,
        "safe_to_write": safe_to_write,
    }


def _stored_frame(
    repository: SqlAlchemyPriceBarRepository,
    instrument_id: int,
    price_basis: str,
) -> pd.DataFrame:
    records = tuple(repository.iter_instrument_bars(InstrumentPriceBarQuery(
        instrument_id=instrument_id,
        price_basis=price_basis,
    )))
    return pd.DataFrame([{
        "date": record.trading_date,
        "open": record.open,
        "high": record.high,
        "low": record.low,
        "close": record.close,
        "volume": record.volume,
        "source": record.source,
    } for record in records])


def run_canary(
    symbol: str,
    start: date,
    end: date,
    *,
    write: bool = False,
    database_url: str | None = None,
) -> dict[str, Any]:
    normalized_symbol = symbol.upper().strip()
    provider = create_vietnam_market_provider(require_sponsored=True)
    provider_result = provider.ohlcv(normalized_symbol, start, end, interval="1D")
    sponsored = normalize_ohlcv_result(provider_result)
    engine = create_db_engine(database_url)
    with Session(engine) as session:
        repository = SqlAlchemyPriceBarRepository(session)
        metadata = SqlAlchemyInstrumentRoutingRepository(
            session
        ).find_instrument_route_metadata("listing", normalized_symbol)
        if metadata is None:
            raise RuntimeError(f"Unknown listing symbol: {normalized_symbol}")
        route = resolve_instrument_data_route(metadata)
        if route.price_adapter != "vnstock_data":
            raise RuntimeError(f"{normalized_symbol} is not routed to vnstock_data")
        stored = _stored_frame(repository, metadata.instrument_id, route.price_basis)
    comparison = compare_frames(sponsored, stored)
    result: dict[str, Any] = {
        "symbol": normalized_symbol,
        "requested_start": start.isoformat(),
        "requested_end": end.isoformat(),
        "source": str(sponsored["provider_source"].iloc[-1]),
        "comparison": comparison,
        "write_requested": write,
        "write_performed": False,
    }
    if not write:
        return result
    if not comparison["safe_to_write"]:
        raise RuntimeError(
            "Sponsored OHLCV comparison failed; canonical prices were not changed"
        )

    fetched_at = datetime.now(UTC).replace(microsecond=0)
    source = result["source"]
    with Session(engine) as session, session.begin():
        service = PriceRefreshService(SqlAlchemyPriceBarRepository(session))
        write_result = service.store_frames(
            "VNALL",
            [sponsored.drop(columns=["provider_source"])],
            targets_by_provider_symbol={
                route.provider_symbol: PriceRefreshTarget(
                    instrument_id=metadata.instrument_id,
                    canonical_symbol=metadata.canonical_symbol,
                    provider_symbol=route.provider_symbol,
                    price_adapter=route.price_adapter,
                    price_basis=route.price_basis,
                    currency=route.currency,
                    price_scale=route.price_scale,
                )
            },
            source=source,
            fetched_at=fetched_at,
        )
        service.record_attempts([PriceRefreshAttempt(
            instrument_id=metadata.instrument_id,
            price_basis=route.price_basis,
            attempted_through=end,
            returned_through=pd.to_datetime(sponsored["date"]).max().date(),
            outcome=(
                "current"
                if pd.to_datetime(sponsored["date"]).max().date() >= end
                else "checked_no_new_bar"
            ),
            primary_source=source,
            selected_source=source,
            attempted_at=fetched_at,
            detail="sponsored FPT canary comparison passed before upsert",
        )])
    result["write_performed"] = True
    result["write_result"] = {
        "input_rows": write_result.input_rows,
        "rejected_rows": write_result.rejected_rows,
        "stored_rows": write_result.stored_rows,
    }
    with Session(engine) as session:
        coverage = SqlAlchemyPriceBarRepository(session).get_instrument_coverage(
            metadata.instrument_id, route.price_basis
        )
    result["stored_coverage"] = (
        {
            "first_date": coverage.first_date.isoformat(),
            "last_date": coverage.last_date.isoformat(),
            "row_count": coverage.row_count,
            "source": coverage.source,
        }
        if coverage is not None
        else None
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="FPT")
    parser.add_argument("--start", type=date.fromisoformat, default=date(2000, 1, 1))
    parser.add_argument("--end", type=date.fromisoformat)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--database-url")
    args = parser.parse_args()
    end = args.end or latest_completed_venue_session(
        datetime.now(UTC), venue_calendar("HOSE")
    )
    result = run_canary(
        args.symbol,
        args.start,
        end,
        write=args.write,
        database_url=args.database_url,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
