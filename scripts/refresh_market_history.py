"""Refresh canonical US and Vietnam OHLCV history in PostgreSQL.

Usage:
    uv run python -m scripts.refresh_market_history --market all
    uv run python -m scripts.refresh_market_history --market us500
    uv run python -m scripts.refresh_market_history --market us2000
    uv run python -m scripts.refresh_market_history --market us100
    uv run python -m scripts.refresh_market_history --market vnall
    uv run python -m scripts.refresh_market_history --market vn30
    uv run python -m scripts.refresh_market_history --market vnmid
    uv run python -m scripts.refresh_market_history --market vnsml
    uv run python -m scripts.refresh_market_history --market vn100
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import json
import time

import pandas as pd
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from api.benchmark_history import (
    DEFAULT_BENCHMARK_DIR,
    save_benchmark_history,
)
from api.db.session import create_db_engine
from api.market_data_config import DEFAULT_REFRESH_CHECKPOINT_DIR, PROJECT_ROOT
from api.market_sessions import latest_completed_session
from api.repositories.sqlalchemy_price_bar_repository import (
    SqlAlchemyPriceBarRepository,
)
from api.services.price_refresh_service import PriceRefreshService
from api.services.price_refresh_service import PriceRefreshAttempt


SNAPSHOT_DIR = PROJECT_ROOT / "api" / "data" / "symbol_lists"
US_MAX_HISTORY_START = date(1900, 1, 1)
VN_MAX_HISTORY_START = date(2000, 1, 1)
INCREMENTAL_OVERLAP_DAYS = 7
US_DOWNLOAD_BATCH_SIZE = 100
BENCHMARK_SYMBOLS = {"SPX": "^GSPC", "VN30": "VN30"}
VN_REFRESH_ORDER = ("VNALL", "VN100", "VN30", "VNMID", "VNSML")
VN_PRIMARY_SOURCE = "KBS"
VN_FALLBACK_SOURCE = "VCI"
VN_PROVIDER_LABELS = {
    "KBS": "vnstock-kbs",
    "VCI": "vnstock-vci",
}


@dataclass(frozen=True)
class VNFetchResult:
    symbol: str
    frame: pd.DataFrame | None
    returned_through: date | None
    outcome: str
    selected_source: str | None
    detail: str


def _symbols(universe: str) -> list[str]:
    snapshot = json.loads((SNAPSHOT_DIR / f"{universe.lower()}.json").read_text())
    key = "yfinance_symbol" if universe.startswith("US") else "symbol"
    if symbols_file := snapshot.get("symbols_file"):
        with (SNAPSHOT_DIR / str(symbols_file)).open(newline="") as handle:
            rows = list(csv.DictReader(handle))
    else:
        rows = snapshot["symbols"]
    return [str(row[key]) for row in rows]


def _normalise_frame(
    raw: pd.DataFrame,
    symbol: str,
    *,
    provider_source: str | None = None,
) -> pd.DataFrame:
    frame = raw.copy()
    frame.columns = [str(column).lower() for column in frame.columns]
    if "time" in frame.columns:
        frame = frame.rename(columns={"time": "date"})
    elif "date" not in frame.columns:
        frame = frame.reset_index()
        frame = frame.rename(columns={str(frame.columns[0]): "date"})
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    frame["symbol"] = symbol
    if provider_source is not None:
        frame["provider_source"] = provider_source
    columns = ["symbol", "date", "open", "high", "low", "close", "volume"]
    if provider_source is not None:
        columns.append("provider_source")
    return frame[[column for column in columns if column in frame.columns]].dropna(
        subset=["open", "high", "low", "close"]
    )


def _latest_frame_date(frame: pd.DataFrame) -> date:
    return pd.to_datetime(frame["date"]).max().date()


def _provider_comparison(
    primary: pd.DataFrame,
    fallback: pd.DataFrame,
) -> str:
    columns = [
        column
        for column in ("open", "high", "low", "close", "volume")
        if column in primary.columns and column in fallback.columns
    ]
    left = primary.copy()
    right = fallback.copy()
    left["date"] = pd.to_datetime(left["date"]).dt.date
    right["date"] = pd.to_datetime(right["date"]).dt.date
    overlap = left.merge(right, on="date", suffixes=("_kbs", "_vci"))
    if overlap.empty:
        return "no overlapping provider rows"
    mismatched = pd.Series(False, index=overlap.index)
    for column in columns:
        left_column = pd.to_numeric(overlap[f"{column}_kbs"], errors="coerce")
        right_column = pd.to_numeric(overlap[f"{column}_vci"], errors="coerce")
        mismatched |= ~left_column.fillna(-1).round(6).eq(
            right_column.fillna(-1).round(6)
        )
    return f"provider overlap={len(overlap)} mismatched={int(mismatched.sum())}"


def _fetch_vn_history(
    quote_factory,
    symbol: str,
    start: date,
    end: date,
    *,
    fallback_delay: float,
) -> VNFetchResult:
    candidates: dict[str, pd.DataFrame] = {}
    errors: list[str] = []

    def fetch(source: str) -> None:
        try:
            raw = quote_factory(symbol=symbol, source=source).history(
                start=start.isoformat(),
                end=end.isoformat(),
                interval="1D",
            )
            if raw is None or raw.empty:
                raise ValueError("empty history")
            candidates[source] = _normalise_frame(
                raw,
                symbol,
                provider_source=VN_PROVIDER_LABELS[source],
            )
        except Exception as exc:
            errors.append(f"{source}: {type(exc).__name__}: {exc}")

    fetch(VN_PRIMARY_SOURCE)
    primary = candidates.get(VN_PRIMARY_SOURCE)
    primary_is_current = primary is not None and _latest_frame_date(primary) >= end
    if not primary_is_current:
        if fallback_delay > 0:
            time.sleep(fallback_delay)
        fetch(VN_FALLBACK_SOURCE)

    if not candidates:
        return VNFetchResult(
            symbol=symbol,
            frame=None,
            returned_through=None,
            outcome="failed",
            selected_source=None,
            detail="; ".join(errors)[:1000],
        )

    selected_source, selected_frame = max(
        candidates.items(),
        key=lambda item: (
            _latest_frame_date(item[1]),
            item[0] == VN_PRIMARY_SOURCE,
        ),
    )
    returned_through = _latest_frame_date(selected_frame)
    detail_parts = [
        f"{source} through {_latest_frame_date(frame).isoformat()}"
        for source, frame in candidates.items()
    ]
    if primary is not None and VN_FALLBACK_SOURCE in candidates:
        detail_parts.append(
            _provider_comparison(primary, candidates[VN_FALLBACK_SOURCE])
        )
    detail_parts.extend(errors)
    return VNFetchResult(
        symbol=symbol,
        frame=selected_frame,
        returned_through=returned_through,
        outcome=("current" if returned_through >= end else "checked_no_new_bar"),
        selected_source=VN_PROVIDER_LABELS[selected_source],
        detail="; ".join(detail_parts)[:1000],
    )


def _existing_benchmark(benchmark: str) -> pd.DataFrame:
    path = DEFAULT_BENCHMARK_DIR / f"{benchmark.lower()}.csv"
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path, parse_dates=["date"])
    frame["symbol"] = BENCHMARK_SYMBOLS[benchmark]
    return frame


def _latest_expected_session(end: date) -> date:
    expected = end
    while expected.weekday() >= 5:
        expected -= timedelta(days=1)
    return expected


def _market_download_plan(
    existing: pd.DataFrame,
    symbols: list[str],
    full_start: date,
    end: date,
    mode: str,
    *,
    assume_existing_complete: bool = False,
    market: str = "VN",
) -> dict[date, list[str]]:
    """Group stale symbols by the first date that still needs downloading."""
    expected_date = end - timedelta(days=1) if market == "US" else end
    expected_latest = _latest_expected_session(expected_date)
    grouped: dict[date, list[str]] = {}
    rows_by_symbol = (
        {str(symbol): rows for symbol, rows in existing.groupby("symbol", sort=False)}
        if not existing.empty
        else {}
    )
    for symbol in symbols:
        rows = rows_by_symbol.get(symbol)
        if rows is None or rows.empty:
            start = full_start
        else:
            if mode == "full" and assume_existing_complete:
                continue
            first_cached = pd.to_datetime(rows["date"]).min().date()
            last_cached = pd.to_datetime(rows["date"]).max().date()
            complete_history = first_cached <= full_start + timedelta(days=14)
            if last_cached >= expected_latest and (mode != "full" or complete_history):
                continue
            start = (
                full_start
                if mode == "full" and not complete_history
                else max(
                    full_start,
                    last_cached - timedelta(days=INCREMENTAL_OVERLAP_DAYS),
                )
            )
        grouped.setdefault(start, []).append(symbol)
    return grouped


def _merge_cache(
    existing: pd.DataFrame,
    fetched: list[pd.DataFrame],
    symbols: list[str],
) -> pd.DataFrame:
    frames = ([existing] if not existing.empty else []) + fetched
    if not frames:
        raise RuntimeError("Refresh returned no price history")
    data = pd.concat(frames, ignore_index=True)
    data = data[data["symbol"].astype(str).isin(symbols)]
    return data.sort_values(["symbol", "date"]).drop_duplicates(
        ["symbol", "date"],
        keep="last",
    )


def _download_us_batch(
    universe: str,
    symbols: list[str],
    start: date,
    end: date,
    *,
    progress_offset: int = 0,
    progress_total: int | None = None,
) -> tuple[list[pd.DataFrame], list[dict[str, str]]]:
    import yfinance as yf

    raw = yf.download(
        tickers=symbols,
        start=start.isoformat(),
        end=(end + timedelta(days=1)).isoformat(),
        auto_adjust=True,
        group_by="ticker",
        threads=5,
        progress=False,
        timeout=20,
    )
    frames: list[pd.DataFrame] = []
    errors: list[dict[str, str]] = []
    for index, symbol in enumerate(symbols, start=1):
        try:
            symbol_frame = (
                raw[symbol] if isinstance(raw.columns, pd.MultiIndex) else raw
            ).dropna(how="all")
            if symbol_frame.empty:
                raise ValueError("empty history")
            frames.append(_normalise_frame(symbol_frame, symbol))
        except Exception as exc:
            errors.append({"symbol": symbol, "error": str(exc)})
        completed = progress_offset + index
        total = progress_total or len(symbols)
        if completed % 10 == 0 or index == len(symbols):
            print(f"{universe}: {completed}/{total} errors={len(errors)}", flush=True)
    return frames, errors


def refresh_benchmark(
    benchmark: str,
    full_start: date,
    end: date,
    mode: str,
) -> None:
    """Refresh one shared index cache used by the relative-strength overlay."""
    provider_symbol = BENCHMARK_SYMBOLS[benchmark]
    existing = _existing_benchmark(benchmark)
    plan = _market_download_plan(
        existing,
        [provider_symbol],
        full_start,
        end,
        mode,
        market="US" if benchmark == "SPX" else "VN",
    )
    frames: list[pd.DataFrame] = []
    if plan:
        start = next(iter(plan))
        if benchmark == "SPX":
            frames, errors = _download_us_batch(
                "SPX benchmark", [provider_symbol], start, end
            )
            if errors:
                raise RuntimeError(f"SPX benchmark refresh failed: {errors}")
            source = "yfinance"
            price_basis = "auto-adjusted OHLC"
        else:
            from vnstock import Quote

            raw = Quote(symbol=provider_symbol, source="VCI").history(
                start=start.isoformat(),
                end=end.isoformat(),
                interval="1D",
            )
            if raw is None or raw.empty:
                raise RuntimeError("VN30 benchmark refresh returned empty history")
            frames = [_normalise_frame(raw, provider_symbol)]
            source = "vnstock-vci"
            price_basis = "provider OHLC (adjustment unspecified)"
    else:
        source = "yfinance" if benchmark == "SPX" else "vnstock-vci"
        price_basis = (
            "auto-adjusted OHLC"
            if benchmark == "SPX"
            else "provider OHLC (adjustment unspecified)"
        )

    data = _merge_cache(existing, frames, [provider_symbol])
    cached = data.drop(columns=["symbol"])
    manifest = {
        "benchmark": benchmark,
        "provider_symbol": provider_symbol,
        "fetched_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "first_date": str(pd.to_datetime(cached["date"]).min().date()),
        "last_date": str(pd.to_datetime(cached["date"]).max().date()),
        "row_count": len(cached),
        "source": source,
        "price_basis": price_basis,
    }
    save_benchmark_history(benchmark, cached, manifest)
    print(f"{benchmark} benchmark: cached {len(cached)} rows", flush=True)


def refresh_us_market(
    engine: Engine,
    universe: str,
    full_start: date,
    end: date,
    mode: str,
    *,
    already_refreshed: set[str] | None = None,
) -> set[str]:
    symbols = _symbols(universe)
    with Session(engine) as session:
        service = PriceRefreshService(SqlAlchemyPriceBarRepository(session))
        plan = service.plan(
            universe,
            symbols,
            full_start=full_start,
            end=end,
            mode=mode,
            already_refreshed=already_refreshed,
        )
    grouped_plan: dict[date, list[str]] = {}
    for symbol, start in plan.requested_starts.items():
        grouped_plan.setdefault(start, []).append(symbol)
    download_total = len(plan.requested_starts)
    reused = len(symbols) - download_total
    print(
        f"{universe}: reusing {reused}/{len(symbols)} symbols from PostgreSQL; "
        f"downloading {download_total}",
        flush=True,
    )

    frames: list[pd.DataFrame] = []
    errors: list[dict[str, str]] = []
    progress_offset = 0
    for start, group in sorted(grouped_plan.items()):
        for chunk_start in range(0, len(group), US_DOWNLOAD_BATCH_SIZE):
            chunk = group[chunk_start:chunk_start + US_DOWNLOAD_BATCH_SIZE]
            group_frames, group_errors = _download_us_batch(
                universe,
                chunk,
                start,
                end,
                progress_offset=progress_offset,
                progress_total=download_total,
            )
            frames.extend(group_frames)
            errors.extend(group_errors)
            progress_offset += len(chunk)

    allowed_failures = max(3, int(len(symbols) * 0.02))
    if len(errors) > allowed_failures:
        raise RuntimeError(
            f"{universe} refresh failed for {len(errors)} symbols: {errors}"
        )

    fetched_at = datetime.now(timezone.utc).replace(microsecond=0)
    with Session(engine) as session:
        with session.begin():
            stored = PriceRefreshService(
                SqlAlchemyPriceBarRepository(session)
            ).store_frames(
                universe,
                frames,
                source="yfinance",
                fetched_at=fetched_at,
            )
    print(
        f"{universe}: stored={stored.stored_rows} rejected={stored.rejected_rows} "
        f"errors={len(errors)}",
        flush=True,
    )
    failed_symbols = {str(error["symbol"]) for error in errors}
    return set(symbols) - failed_symbols


def refresh_vn_market(
    engine: Engine,
    universe: str,
    full_start: date,
    end: date,
    delay: float,
    mode: str,
    *,
    already_refreshed: set[str] | None = None,
) -> set[str]:
    from vnstock import Quote

    symbols = _symbols(universe)
    with Session(engine) as session:
        plan = PriceRefreshService(
            SqlAlchemyPriceBarRepository(session)
        ).plan(
            universe,
            symbols,
            full_start=full_start,
            end=end,
            mode=mode,
            already_refreshed=already_refreshed,
        )
    start_by_symbol = plan.requested_starts
    requested_symbols = [symbol for symbol in symbols if symbol in start_by_symbol]
    download_total = len(requested_symbols)
    reused = len(symbols) - download_total
    print(
        f"{universe}: reusing {reused}/{len(symbols)} symbols from PostgreSQL; "
        f"downloading {download_total}",
        flush=True,
    )

    stem = universe.lower()
    checkpoint_path = DEFAULT_REFRESH_CHECKPOINT_DIR / f"{stem}.refresh.csv"
    checkpoint_manifest_path = DEFAULT_REFRESH_CHECKPOINT_DIR / f"{stem}.refresh.json"
    DEFAULT_REFRESH_CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    frames: list[pd.DataFrame] = []
    errors: list[dict[str, str]] = []
    completed_symbols: set[str] = set()

    if checkpoint_path.exists() and checkpoint_manifest_path.exists():
        checkpoint_manifest = json.loads(checkpoint_manifest_path.read_text())
        if (
            checkpoint_manifest.get("start") == full_start.isoformat()
            and checkpoint_manifest.get("end") == end.isoformat()
            and checkpoint_manifest.get("mode") == mode
            and checkpoint_manifest.get("source") == "KBS->VCI"
        ):
            checkpoint = pd.read_csv(checkpoint_path, parse_dates=["date"])
            checkpoint = checkpoint[
                checkpoint["symbol"].astype(str).isin(requested_symbols)
            ]
            if not checkpoint.empty:
                frames.append(checkpoint)
            completed_symbols = set(checkpoint["symbol"].astype(str))
            print(
                f"{universe}: resuming {len(completed_symbols)}/{download_total} "
                "symbols from checkpoint",
                flush=True,
            )
        else:
            checkpoint_path.unlink(missing_ok=True)
            checkpoint_manifest_path.unlink(missing_ok=True)

    checkpoint_manifest_path.write_text(
        json.dumps({
            "start": full_start.isoformat(),
            "end": end.isoformat(),
            "mode": mode,
            "source": "KBS->VCI",
        })
    )

    results: dict[str, VNFetchResult] = {}
    for index, symbol in enumerate(requested_symbols, start=1):
        if symbol in completed_symbols:
            continue
        result = _fetch_vn_history(
            Quote,
            symbol,
            start_by_symbol[symbol],
            end,
            fallback_delay=delay,
        )
        results[symbol] = result
        if result.frame is not None:
            frames.append(result.frame)
        else:
            errors.append({"symbol": symbol, "error": result.detail})

        if frames:
            pd.concat(frames, ignore_index=True).to_csv(checkpoint_path, index=False)
        if index % 10 == 0 or index == download_total:
            print(
                f"{universe}: {index}/{download_total} "
                f"errors={len(errors)}",
                flush=True,
            )
        if index < download_total:
            time.sleep(delay)

    fetched_at = datetime.now(timezone.utc).replace(microsecond=0)
    attempts: list[PriceRefreshAttempt] = []
    if frames:
        checkpoint_data = pd.concat(frames, ignore_index=True)
        for symbol, symbol_frame in checkpoint_data.groupby("symbol", sort=False):
            if symbol in results:
                continue
            returned_through = _latest_frame_date(symbol_frame)
            provider_source = str(symbol_frame["provider_source"].iloc[-1])
            results[str(symbol)] = VNFetchResult(
                symbol=str(symbol),
                frame=symbol_frame,
                returned_through=returned_through,
                outcome=(
                    "current" if returned_through >= end else "checked_no_new_bar"
                ),
                selected_source=provider_source,
                detail="resumed from refresh checkpoint",
            )
    for symbol in requested_symbols:
        result = results[symbol]
        attempts.append(PriceRefreshAttempt(
            ticker=symbol,
            attempted_through=end,
            returned_through=result.returned_through,
            outcome=result.outcome,
            primary_source=VN_PROVIDER_LABELS[VN_PRIMARY_SOURCE],
            selected_source=result.selected_source,
            attempted_at=fetched_at,
            detail=result.detail,
        ))

    stored_rows = 0
    rejected_rows = 0
    with Session(engine) as session:
        with session.begin():
            service = PriceRefreshService(SqlAlchemyPriceBarRepository(session))
            if frames:
                data = pd.concat(frames, ignore_index=True)
                for source, source_rows in data.groupby("provider_source"):
                    stored = service.store_frames(
                        universe,
                        [source_rows.drop(columns=["provider_source"])],
                        source=str(source),
                        fetched_at=fetched_at,
                    )
                    stored_rows += stored.stored_rows
                    rejected_rows += stored.rejected_rows
            service.record_attempts(universe, attempts)
    checkpoint_path.unlink(missing_ok=True)
    checkpoint_manifest_path.unlink(missing_ok=True)
    current_count = sum(result.outcome == "current" for result in results.values())
    no_new_count = sum(
        result.outcome == "checked_no_new_bar" for result in results.values()
    )
    print(
        f"{universe}: stored={stored_rows} rejected={rejected_rows} "
        f"errors={len(errors)}",
        flush=True,
    )
    print(
        f"{universe}: result current={current_count} "
        f"checked_no_new={no_new_count} failed={len(errors)} "
        f"attempted_through={end.isoformat()} primary=KBS fallback=VCI",
        flush=True,
    )
    if errors:
        raise RuntimeError(
            f"{universe} refresh failed for {len(errors)} symbols: {errors}"
        )
    return set(symbols)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--market",
        choices=(
            "all", "us500", "us2000", "us100",
            "vnall", "vn100", "vn30", "vnmid", "vnsml",
        ),
        default="all",
    )
    parser.add_argument(
        "--calendar-days",
        type=int,
        default=None,
        help="Optional history limit. By default, full mode requests maximum provider history.",
    )
    parser.add_argument(
        "--mode",
        choices=("incremental", "full"),
        default="full",
    )
    parser.add_argument("--vn-delay", type=float, default=4.1)
    parser.add_argument("--database-url", default=None)
    args = parser.parse_args()
    engine = create_db_engine(args.database_url)

    end = date.today()
    vn_end = latest_completed_session(datetime.now(timezone.utc), "VN")
    if args.calendar_days is None:
        us_full_start = US_MAX_HISTORY_START
        vn_full_start = VN_MAX_HISTORY_START
    else:
        us_full_start = end - timedelta(days=args.calendar_days)
        vn_full_start = vn_end - timedelta(days=args.calendar_days)

    if args.market == "all":
        refresh_benchmark("SPX", us_full_start, end, args.mode)
        refreshed_us = refresh_us_market(
            engine, "US2000", us_full_start, end, args.mode
        )
        refreshed_us |= refresh_us_market(
            engine,
            "US500",
            us_full_start,
            end,
            args.mode,
            already_refreshed=refreshed_us,
        )
        refreshed_us |= refresh_us_market(
            engine,
            "US100",
            us_full_start,
            end,
            args.mode,
            already_refreshed=refreshed_us,
        )
        refresh_benchmark("VN30", vn_full_start, vn_end, args.mode)
        refreshed_vn: set[str] = set()
        for universe in VN_REFRESH_ORDER:
            refreshed_vn |= refresh_vn_market(
                engine,
                universe,
                vn_full_start,
                vn_end,
                args.vn_delay,
                args.mode,
                already_refreshed=refreshed_vn,
            )
        return

    if args.market == "us2000":
        refresh_benchmark("SPX", us_full_start, end, args.mode)
        refresh_us_market(engine, "US2000", us_full_start, end, args.mode)
    elif args.market == "us500":
        refresh_benchmark("SPX", us_full_start, end, args.mode)
        refresh_us_market(engine, "US500", us_full_start, end, args.mode)
    elif args.market == "us100":
        refresh_benchmark("SPX", us_full_start, end, args.mode)
        refresh_us_market(engine, "US100", us_full_start, end, args.mode)
    elif args.market in {"vnall", "vn100", "vn30", "vnmid", "vnsml"}:
        refresh_benchmark("VN30", vn_full_start, vn_end, args.mode)
        refresh_vn_market(
            engine,
            args.market.upper(),
            vn_full_start,
            vn_end,
            args.vn_delay,
            args.mode,
        )


if __name__ == "__main__":
    main()
