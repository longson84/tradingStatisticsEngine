"""One-time import of legacy SPX/VN30 cache files into canonical price bars."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path

import pandas as pd
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from api.db.models import Instrument
from api.db.session import create_db_engine, session_scope
from api.instrument_data_routing import resolve_instrument_data_route
from api.repositories.sqlalchemy_instrument_routing_repository import (
    SqlAlchemyInstrumentRoutingRepository,
)
from api.repositories.sqlalchemy_price_bar_repository import (
    SqlAlchemyPriceBarRepository,
)
from api.services.instrument_price_write_service import InstrumentPriceWriteService
from api.services.price_refresh_service import PriceRefreshAttempt, PriceRefreshService
from trading_engine.types import PriceFrame


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEGACY_CACHE_DIR = PROJECT_ROOT / ".cache" / "benchmark_history"
BENCHMARK_CODES = ("SPX", "VN30")


@dataclass(frozen=True)
class BenchmarkMigrationResult:
    code: str
    instrument_id: int
    first_date: str
    last_date: str
    row_count: int
    source: str


def migrate_legacy_benchmark_cache(
    engine: Engine,
    cache_dir: Path,
    *,
    delete_source: bool = False,
) -> tuple[BenchmarkMigrationResult, ...]:
    prepared = tuple(_read_cache(code, cache_dir) for code in BENCHMARK_CODES)
    results: list[BenchmarkMigrationResult] = []
    source_paths: list[Path] = []
    for code, frame, manifest, paths in prepared:
        with Session(engine) as session:
            instrument = session.scalar(select(Instrument).where(
                Instrument.instrument_type == "market_index",
                Instrument.ticker == code,
                Instrument.is_active.is_(True),
            ))
            if instrument is None:
                raise RuntimeError(
                    f"Missing canonical market-index instrument {code}; "
                    "run alembic upgrade head first"
                )
            metadata = SqlAlchemyInstrumentRoutingRepository(
                session
            ).get_instrument_route_metadata(instrument.id)
        if metadata is None:
            raise RuntimeError(f"Missing routing metadata for {code}")
        route = resolve_instrument_data_route(metadata)
        fetched_at = _timestamp(manifest.get("fetched_at"))
        prices = PriceFrame(
            symbol=route.provider_symbol,
            data=frame.set_index("date"),
            source=str(manifest["source"]),
        )
        with session_scope(engine) as session:
            stored = InstrumentPriceWriteService(
                SqlAlchemyPriceBarRepository(session),
                SqlAlchemyInstrumentRoutingRepository(session),
            ).store_history(instrument.id, prices, fetched_at=fetched_at)
            last_date = frame["date"].max().date()
            PriceRefreshService(
                SqlAlchemyPriceBarRepository(session)
            ).record_attempts([PriceRefreshAttempt(
                instrument_id=instrument.id,
                price_basis=route.price_basis,
                attempted_through=last_date,
                returned_through=last_date,
                outcome="current",
                primary_source=route.price_adapter,
                selected_source=str(manifest["source"]),
                attempted_at=fetched_at,
                detail="migrated from verified legacy benchmark cache",
            )])
        if stored != len(frame):
            raise RuntimeError(
                f"{code} migration affected {stored} rows; expected {len(frame)}"
            )
        results.append(BenchmarkMigrationResult(
            code=code,
            instrument_id=instrument.id,
            first_date=str(frame["date"].min().date()),
            last_date=str(frame["date"].max().date()),
            row_count=len(frame),
            source=str(manifest["source"]),
        ))
        source_paths.extend(paths)
    if delete_source:
        for path in source_paths:
            path.unlink()
        cache_dir.rmdir()
    return tuple(results)


def _read_cache(
    code: str,
    cache_dir: Path,
) -> tuple[str, pd.DataFrame, dict[str, object], tuple[Path, Path]]:
    csv_path = cache_dir / f"{code.lower()}.csv"
    manifest_path = cache_dir / f"{code.lower()}.json"
    if not csv_path.is_file() or not manifest_path.is_file():
        raise RuntimeError(f"Legacy benchmark cache for {code} is incomplete")
    try:
        manifest = json.loads(manifest_path.read_text())
        frame = pd.read_csv(csv_path, parse_dates=["date"])
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        raise RuntimeError(f"Invalid legacy benchmark cache for {code}: {exc}") from exc
    if str(manifest.get("benchmark", "")).upper() != code:
        raise RuntimeError(f"Legacy manifest identity does not match {code}")
    required = {"date", "open", "high", "low", "close"}
    if missing := required - set(frame.columns):
        raise RuntimeError(f"Legacy {code} cache is missing columns: {sorted(missing)}")
    frame = frame.sort_values("date").drop_duplicates("date", keep="last")
    if frame.empty or frame["date"].isna().any():
        raise RuntimeError(f"Legacy {code} cache has no valid dated rows")
    expected_count = int(manifest.get("row_count", -1))
    if expected_count != len(frame):
        raise RuntimeError(
            f"Legacy {code} row count mismatch: {len(frame)} != {expected_count}"
        )
    if not manifest.get("source"):
        raise RuntimeError(f"Legacy {code} manifest has no source")
    return code, frame, manifest, (csv_path, manifest_path)


def _timestamp(value: object) -> datetime:
    parsed = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(parsed):
        return datetime.now(UTC)
    return parsed.to_pydatetime()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_LEGACY_CACHE_DIR)
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--delete-source", action="store_true")
    args = parser.parse_args()
    results = migrate_legacy_benchmark_cache(
        create_db_engine(args.database_url),
        args.cache_dir,
        delete_source=args.delete_source,
    )
    for result in results:
        print(
            f"{result.code}: instrument={result.instrument_id} "
            f"rows={result.row_count} {result.first_date}..{result.last_date} "
            f"source={result.source}",
            flush=True,
        )


if __name__ == "__main__":
    main()
