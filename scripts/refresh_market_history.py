"""Refresh persistent US and Vietnam OHLCV market-health caches.

Usage:
    uv run python -m scripts.refresh_market_history --market all
    uv run python -m scripts.refresh_market_history --market us500
    uv run python -m scripts.refresh_market_history --market us2000
    uv run python -m scripts.refresh_market_history --market us100
    uv run python -m scripts.refresh_market_history --market vn30
    uv run python -m scripts.refresh_market_history --market vn100
"""
from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timedelta, timezone
import json
import time

import pandas as pd

from api.benchmark_history import (
    DEFAULT_BENCHMARK_DIR,
    save_benchmark_history,
)
from api.market_history import DEFAULT_CACHE_DIR, PROJECT_ROOT, save_market_history


SNAPSHOT_DIR = PROJECT_ROOT / "api" / "data" / "symbol_lists"
US_MAX_HISTORY_START = date(1900, 1, 1)
VN_MAX_HISTORY_START = date(2000, 1, 1)
INCREMENTAL_OVERLAP_DAYS = 7
US_DOWNLOAD_BATCH_SIZE = 100
BENCHMARK_SYMBOLS = {"SPX": "^GSPC", "VN30": "VN30"}


def _symbols(universe: str) -> list[str]:
    snapshot = json.loads((SNAPSHOT_DIR / f"{universe.lower()}.json").read_text())
    key = "yfinance_symbol" if universe.startswith("US") else "symbol"
    if symbols_file := snapshot.get("symbols_file"):
        with (SNAPSHOT_DIR / str(symbols_file)).open(newline="") as handle:
            rows = list(csv.DictReader(handle))
    else:
        rows = snapshot["symbols"]
    return [str(row[key]) for row in rows]


def _normalise_frame(raw: pd.DataFrame, symbol: str) -> pd.DataFrame:
    frame = raw.copy()
    frame.columns = [str(column).lower() for column in frame.columns]
    if "time" in frame.columns:
        frame = frame.rename(columns={"time": "date"})
    elif "date" not in frame.columns:
        frame = frame.reset_index()
        frame = frame.rename(columns={str(frame.columns[0]): "date"})
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    frame["symbol"] = symbol
    columns = ["symbol", "date", "open", "high", "low", "close", "volume"]
    return frame[[column for column in columns if column in frame.columns]].dropna(
        subset=["open", "high", "low", "close"]
    )


def _manifest(
    universe: str,
    data: pd.DataFrame,
    *,
    source: str,
    price_basis: str,
    errors: list[dict[str, str]],
) -> dict:
    return {
        "universe": universe,
        "fetched_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "first_date": str(pd.to_datetime(data["date"]).min().date()),
        "last_date": str(pd.to_datetime(data["date"]).max().date()),
        "symbol_count": int(data["symbol"].nunique()),
        "row_count": len(data),
        "source": source,
        "price_basis": price_basis,
        "errors": errors,
    }


def _existing_cache(universe: str) -> pd.DataFrame:
    path = DEFAULT_CACHE_DIR / f"{universe.lower()}.csv"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, parse_dates=["date"])


def _existing_benchmark(benchmark: str) -> pd.DataFrame:
    path = DEFAULT_BENCHMARK_DIR / f"{benchmark.lower()}.csv"
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path, parse_dates=["date"])
    frame["symbol"] = BENCHMARK_SYMBOLS[benchmark]
    return frame


def _reusable_history(
    universe: str,
    symbols: list[str],
    *,
    include_target: bool,
    universe_group: tuple[str, ...],
) -> pd.DataFrame:
    """Combine related caches, preferring the freshest cache per symbol."""
    cache_order = [candidate for candidate in universe_group if candidate != universe]
    if include_target:
        cache_order.append(universe)

    candidates: list[pd.DataFrame] = []
    for priority, candidate in enumerate(cache_order):
        frame = _existing_cache(candidate)
        if frame.empty:
            continue
        frame = frame[frame["symbol"].astype(str).isin(symbols)].copy()
        if frame.empty:
            continue
        frame["_cache_last"] = frame.groupby("symbol")["date"].transform("max")
        frame["_source_priority"] = priority
        candidates.append(frame)

    if not candidates:
        return pd.DataFrame()
    combined = pd.concat(candidates, ignore_index=True)
    combined = combined.sort_values(
        ["symbol", "date", "_cache_last", "_source_priority"]
    ).drop_duplicates(["symbol", "date"], keep="last")
    return combined.drop(columns=["_cache_last", "_source_priority"])


def _reusable_us_history(
    universe: str,
    symbols: list[str],
    *,
    include_target: bool,
    reuse_from: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    return _reusable_history(
        universe,
        symbols,
        include_target=include_target,
        universe_group=(
            ("US500", "US2000", "US100")
            if reuse_from is None
            else reuse_from
        ),
    )


def _reusable_vn_history(
    universe: str,
    symbols: list[str],
    *,
    include_target: bool,
    reuse_from: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    return _reusable_history(
        universe,
        symbols,
        include_target=include_target,
        universe_group=("VN100", "VN30") if reuse_from is None else reuse_from,
    )


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
) -> dict[date, list[str]]:
    """Group stale symbols by the first date that still needs downloading."""
    expected_latest = _latest_expected_session(end)
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
    universe: str,
    full_start: date,
    end: date,
    mode: str,
    *,
    reuse_from: tuple[str, ...] | None = None,
) -> None:
    symbols = _symbols(universe)
    existing = _reusable_us_history(
        universe,
        symbols,
        include_target=mode == "incremental",
        reuse_from=reuse_from,
    )
    plan = _market_download_plan(
        existing,
        symbols,
        full_start,
        end,
        mode,
        assume_existing_complete=mode == "full" and reuse_from is not None,
    )
    download_total = sum(len(group) for group in plan.values())
    reused = len(symbols) - download_total
    print(
        f"{universe}: reusing {reused}/{len(symbols)} symbols from US caches; "
        f"downloading {download_total}",
        flush=True,
    )

    frames: list[pd.DataFrame] = []
    errors: list[dict[str, str]] = []
    progress_offset = 0
    for start, group in sorted(plan.items()):
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

    data = _merge_cache(existing, frames, symbols)
    save_market_history(
        universe,
        data,
        _manifest(
            universe,
            data,
            source="yfinance",
            price_basis="auto-adjusted OHLC",
            errors=errors,
        ),
    )
    print(
        f"{universe}: cached {data['symbol'].nunique()} symbols; errors={len(errors)}",
        flush=True,
    )


def refresh_vn_market(
    universe: str,
    full_start: date,
    end: date,
    delay: float,
    mode: str,
    *,
    reuse_from: tuple[str, ...] | None = None,
) -> None:
    from vnstock import Quote

    symbols = _symbols(universe)
    existing = _reusable_vn_history(
        universe,
        symbols,
        include_target=mode == "incremental",
        reuse_from=reuse_from,
    )
    plan = _market_download_plan(
        existing,
        symbols,
        full_start,
        end,
        mode,
        assume_existing_complete=mode == "full" and reuse_from is not None,
    )
    start_by_symbol = {
        symbol: start
        for start, group in plan.items()
        for symbol in group
    }
    requested_symbols = [symbol for symbol in symbols if symbol in start_by_symbol]
    download_total = len(requested_symbols)
    reused = len(symbols) - download_total
    print(
        f"{universe}: reusing {reused}/{len(symbols)} symbols from VN caches; "
        f"downloading {download_total}",
        flush=True,
    )

    stem = universe.lower()
    checkpoint_path = DEFAULT_CACHE_DIR / f"{stem}.refresh.csv"
    checkpoint_manifest_path = DEFAULT_CACHE_DIR / f"{stem}.refresh.json"
    DEFAULT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    frames: list[pd.DataFrame] = []
    errors: list[dict[str, str]] = []
    completed_symbols: set[str] = set()

    if checkpoint_path.exists() and checkpoint_manifest_path.exists():
        checkpoint_manifest = json.loads(checkpoint_manifest_path.read_text())
        if (
            checkpoint_manifest.get("start") == full_start.isoformat()
            and checkpoint_manifest.get("end") == end.isoformat()
            and checkpoint_manifest.get("mode") == mode
            and checkpoint_manifest.get("source") == "VCI"
        ):
            checkpoint = pd.read_csv(checkpoint_path, parse_dates=["date"])
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
            "source": "VCI",
        })
    )

    for index, symbol in enumerate(requested_symbols, start=1):
        if symbol in completed_symbols:
            continue
        try:
            raw = Quote(symbol=symbol, source="VCI").history(
                start=start_by_symbol[symbol].isoformat(),
                end=end.isoformat(),
                interval="1D",
            )
            if raw is None or raw.empty:
                raise ValueError("empty history")
            frames.append(_normalise_frame(raw, symbol))
        except Exception as exc:
            errors.append({"symbol": symbol, "error": str(exc)})

        if frames:
            pd.concat(frames, ignore_index=True).to_csv(checkpoint_path, index=False)
        downloaded_count = len(
            set(pd.concat(frames, ignore_index=True)["symbol"].astype(str))
        ) if frames else 0
        if downloaded_count % 10 == 0 or downloaded_count == download_total:
            print(
                f"{universe}: {downloaded_count}/{download_total} "
                f"errors={len(errors)}",
                flush=True,
            )
        if index < download_total:
            time.sleep(delay)

    if errors:
        raise RuntimeError(
            f"{universe} refresh failed for {len(errors)} symbols: {errors}"
        )

    data = _merge_cache(existing, frames, symbols)
    save_market_history(
        universe,
        data,
        _manifest(
            universe,
            data,
            source="vnstock-vci",
            price_basis="provider OHLC (adjustment unspecified)",
            errors=errors,
        ),
    )
    checkpoint_path.unlink(missing_ok=True)
    checkpoint_manifest_path.unlink(missing_ok=True)
    print(
        f"{universe}: cached {data['symbol'].nunique()} symbols; errors=0",
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--market",
        choices=("all", "us500", "us2000", "us100", "vn100", "vn30"),
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
    args = parser.parse_args()

    end = date.today()
    if args.calendar_days is None:
        us_full_start = US_MAX_HISTORY_START
        vn_full_start = VN_MAX_HISTORY_START
    else:
        us_full_start = end - timedelta(days=args.calendar_days)
        vn_full_start = us_full_start

    if args.market == "all":
        refresh_benchmark("SPX", us_full_start, end, args.mode)
        refresh_us_market(
            "US2000", us_full_start, end, args.mode, reuse_from=()
        )
        refresh_us_market(
            "US500", us_full_start, end, args.mode, reuse_from=("US2000",)
        )
        refresh_us_market(
            "US100",
            us_full_start,
            end,
            args.mode,
            reuse_from=("US2000", "US500"),
        )
        refresh_benchmark("VN30", vn_full_start, end, args.mode)
        refresh_vn_market(
            "VN100", vn_full_start, end, args.vn_delay, args.mode, reuse_from=()
        )
        refresh_vn_market(
            "VN30",
            vn_full_start,
            end,
            args.vn_delay,
            args.mode,
            reuse_from=("VN100",),
        )
        return

    if args.market == "us2000":
        refresh_benchmark("SPX", us_full_start, end, args.mode)
        refresh_us_market("US2000", us_full_start, end, args.mode)
    elif args.market == "us500":
        refresh_benchmark("SPX", us_full_start, end, args.mode)
        refresh_us_market("US500", us_full_start, end, args.mode)
    elif args.market == "us100":
        refresh_benchmark("SPX", us_full_start, end, args.mode)
        refresh_us_market("US100", us_full_start, end, args.mode)
    elif args.market == "vn100":
        refresh_benchmark("VN30", vn_full_start, end, args.mode)
        refresh_vn_market("VN100", vn_full_start, end, args.vn_delay, args.mode)
    elif args.market == "vn30":
        refresh_benchmark("VN30", vn_full_start, end, args.mode)
        refresh_vn_market("VN30", vn_full_start, end, args.vn_delay, args.mode)


if __name__ == "__main__":
    main()
