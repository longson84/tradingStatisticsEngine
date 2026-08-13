"""Refresh canonical prices for one PostgreSQL Universe.

Usage:
    uv run python -m scripts.refresh_universe_prices --universe <code>
"""
from __future__ import annotations

import argparse
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
from api.config import env_bool, env_float
from api.db.session import create_db_engine
from api.market_data_config import DEFAULT_REFRESH_CHECKPOINT_DIR
from api.repositories.sqlalchemy_data_operation_repository import (
    SqlAlchemyDataOperationRepository,
)
from api.repositories.sqlalchemy_instrument_routing_repository import (
    SqlAlchemyInstrumentRoutingRepository,
)
from api.repositories.sqlalchemy_price_bar_repository import (
    SqlAlchemyPriceBarRepository,
)
from api.services.price_refresh_service import (
    PriceRefreshAttempt,
    PriceRefreshService,
    PriceRefreshTarget,
)
from api.instrument_data_routing import resolve_instrument_data_route
from api.market_sessions import latest_completed_venue_session
from api.providers.vietnam_market import (
    CommunityVnstockProvider,
    VietnamMarketProvider,
    create_vietnam_market_provider,
    normalize_ohlcv_result,
    provider_runtime_label,
    provider_source_label,
)


US_MAX_HISTORY_START = date(1900, 1, 1)
VN_MAX_HISTORY_START = date(2000, 1, 1)
INCREMENTAL_OVERLAP_DAYS = 7
US_DOWNLOAD_BATCH_SIZE = 100
BENCHMARK_SYMBOLS = {"SPX": "^GSPC", "VN30": "VN30"}
DEFAULT_VN_REQUESTS_PER_MINUTE = 30.0


@dataclass(frozen=True)
class VNFetchResult:
    symbol: str
    frame: pd.DataFrame | None
    returned_through: date | None
    outcome: str
    selected_source: str | None
    detail: str


def _scope_instruments(engine: Engine, universe: str):
    """Resolve active universe members from the canonical PostgreSQL catalog."""
    with Session(engine) as session:
        scope = SqlAlchemyDataOperationRepository(session).get_scope(
            "universe", universe
        )
    if scope is None:
        raise RuntimeError(f"Unknown PostgreSQL universe: {universe}")
    if not scope.instruments:
        raise RuntimeError(
            f"PostgreSQL universe {scope.scope_id} has no active members"
        )
    return scope.instruments


def _refresh_targets(engine: Engine, instruments):
    instrument_ids = tuple(row.id for row in instruments)
    with Session(engine) as session:
        metadata = SqlAlchemyInstrumentRoutingRepository(
            session
        ).get_instrument_routes_metadata(instrument_ids)
    routes = {
        row.instrument_id: resolve_instrument_data_route(row) for row in metadata
    }
    if len(routes) != len(instrument_ids):
        missing = sorted(set(instrument_ids) - set(routes))
        raise RuntimeError(f"Missing instrument routing metadata: {missing}")
    return [
        PriceRefreshTarget(
            instrument_id=row.id,
            canonical_symbol=row.symbol,
            provider_symbol=routes[row.id].provider_symbol,
            price_adapter=routes[row.id].price_adapter,
            price_basis=routes[row.id].price_basis,
            currency=routes[row.id].currency,
            price_scale=routes[row.id].price_scale,
        )
        for row in instruments
    ], routes


def _symbols(
    universe: str | Engine,
    engine: Engine | str | None = None,
) -> list[str]:
    """Compatibility projection used by diagnostics and snapshot tests."""
    if isinstance(universe, str):
        universe_code = universe
        resolved_engine = engine if isinstance(engine, Engine) else create_db_engine()
    else:
        if not isinstance(engine, str):
            raise TypeError("Universe code is required")
        resolved_engine = universe
        universe_code = engine
    return [
        instrument.symbol
        for instrument in _scope_instruments(resolved_engine, universe_code)
    ]


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
    overlap = left.merge(right, on="date", suffixes=("_left", "_right"))
    if overlap.empty:
        return "no overlapping provider rows"
    mismatched = pd.Series(False, index=overlap.index)
    for column in columns:
        left_column = pd.to_numeric(overlap[f"{column}_left"], errors="coerce")
        right_column = pd.to_numeric(overlap[f"{column}_right"], errors="coerce")
        mismatched |= ~left_column.fillna(-1).round(6).eq(
            right_column.fillna(-1).round(6)
        )
    return f"provider overlap={len(overlap)} mismatched={int(mismatched.sum())}"


def _fetch_vn_history(
    provider: VietnamMarketProvider,
    symbol: str,
    start: date,
    end: date,
    *,
    community_fallbacks: tuple[CommunityVnstockProvider, ...] = (),
    fallback_delay: float,
) -> VNFetchResult:
    candidates: dict[str, pd.DataFrame] = {}
    errors: list[str] = []

    def fetch(candidate_provider: VietnamMarketProvider) -> None:
        provider_name = _provider_name(candidate_provider)
        try:
            result = candidate_provider.ohlcv(symbol, start, end, interval="1D")
            source = provider_source_label(result.metadata)
            candidates[source] = normalize_ohlcv_result(result)
        except Exception as exc:
            errors.append(f"{provider_name}: {type(exc).__name__}: {exc}")

    fetch(provider)
    primary_source = next(iter(candidates), None)
    primary = candidates.get(primary_source) if primary_source else None
    primary_is_current = primary is not None and _latest_frame_date(primary) >= end
    if not primary_is_current:
        for fallback in community_fallbacks:
            if fallback_delay > 0:
                time.sleep(fallback_delay)
            fetch(fallback)
            if any(_latest_frame_date(frame) >= end for frame in candidates.values()):
                break

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
        key=lambda item: _latest_frame_date(item[1]),
    )
    returned_through = _latest_frame_date(selected_frame)
    detail_parts = [
        f"{source} through {_latest_frame_date(frame).isoformat()}"
        for source, frame in candidates.items()
    ]
    if primary is not None and len(candidates) > 1:
        for source, frame in candidates.items():
            if source != primary_source:
                detail_parts.append(
                    f"{primary_source} vs {source}: "
                    f"{_provider_comparison(primary, frame)}"
                )
    detail_parts.extend(errors)
    return VNFetchResult(
        symbol=symbol,
        frame=selected_frame,
        returned_through=returned_through,
        outcome=("current" if returned_through >= end else "checked_no_new_bar"),
        selected_source=selected_source,
        detail="; ".join(detail_parts)[:1000],
    )


def _provider_name(provider: VietnamMarketProvider) -> str:
    return provider_runtime_label(provider)


def _community_fallbacks(enabled: bool) -> tuple[CommunityVnstockProvider, ...]:
    if not enabled:
        return ()
    return (
        CommunityVnstockProvider(source="KBS"),
        CommunityVnstockProvider(source="VCI"),
    )


def _existing_benchmark(benchmark: str) -> pd.DataFrame:
    path = DEFAULT_BENCHMARK_DIR / f"{benchmark.lower()}.csv"
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path, parse_dates=["date"])
    frame["symbol"] = BENCHMARK_SYMBOLS[benchmark]
    return frame


def _existing_benchmark_manifest(benchmark: str) -> dict[str, object]:
    path = DEFAULT_BENCHMARK_DIR / f"{benchmark.lower()}.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _assert_benchmark_parity(
    existing: pd.DataFrame,
    sponsored: pd.DataFrame,
) -> None:
    """Block cache replacement when sponsored history changes stored bars."""
    if existing.empty:
        return
    left = existing.copy()
    right = sponsored.copy()
    left["date"] = pd.to_datetime(left["date"]).dt.date
    right["date"] = pd.to_datetime(right["date"]).dt.date
    missing_dates = set(left["date"]) - set(right["date"])
    overlap = left.merge(right, on="date", suffixes=("_stored", "_sponsored"))
    mismatched = pd.Series(False, index=overlap.index)
    for column in ("open", "high", "low", "close", "volume"):
        if column not in left or column not in right:
            continue
        stored = pd.to_numeric(overlap[f"{column}_stored"], errors="coerce")
        candidate = pd.to_numeric(
            overlap[f"{column}_sponsored"], errors="coerce"
        )
        mismatched |= ~stored.fillna(-1).round(6).eq(
            candidate.fillna(-1).round(6)
        )
    if missing_dates or mismatched.any():
        raise RuntimeError(
            "Sponsored VN30 benchmark comparison failed: "
            f"missing_dates={len(missing_dates)} "
            f"mismatched_rows={int(mismatched.sum())}"
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
    end_is_exclusive: bool = False,
) -> dict[date, list[str]]:
    """Group stale symbols by the first date that still needs downloading."""
    expected_date = end - timedelta(days=1) if end_is_exclusive else end
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
    *,
    vn_provider: VietnamMarketProvider | None = None,
) -> None:
    """Refresh one shared index cache used by the relative-strength overlay."""
    provider_symbol = BENCHMARK_SYMBOLS[benchmark]
    existing = _existing_benchmark(benchmark)
    existing_manifest = _existing_benchmark_manifest(benchmark)
    plan = _market_download_plan(
        existing,
        [provider_symbol],
        full_start,
        end,
        mode,
        end_is_exclusive=benchmark == "SPX",
    )
    frames: list[pd.DataFrame] = []
    sponsored_provider: VietnamMarketProvider | None = None
    sponsored_source: str | None = None
    if benchmark == "VN30":
        sponsored_provider = vn_provider or create_vietnam_market_provider(
            require_sponsored=True
        )
        sponsored_source = _provider_name(sponsored_provider)
        if not existing.empty and existing_manifest.get("source") != sponsored_source:
            plan = {full_start: [provider_symbol]}
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
            assert sponsored_provider is not None
            result = sponsored_provider.ohlcv(
                provider_symbol,
                start,
                end,
                interval="1D",
            )
            normalized = normalize_ohlcv_result(result).drop(
                columns=["provider_source"]
            )
            _assert_benchmark_parity(existing, normalized)
            frames = [normalized]
            source = provider_source_label(result.metadata)
            price_basis = "provider OHLC (adjustment unspecified)"
    else:
        source = "yfinance" if benchmark == "SPX" else str(sponsored_source)
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
    already_refreshed: set[int] | None = None,
) -> set[int]:
    instruments = _scope_instruments(engine, universe)
    targets, routes = _refresh_targets(engine, instruments)
    if {target.price_adapter for target in targets} != {"yfinance"}:
        raise RuntimeError(f"{universe} is not a yfinance equity universe")
    end = min(
        end,
        latest_completed_venue_session(
            datetime.now(timezone.utc), next(iter(routes.values())).schedule
        ),
    )
    targets_by_id = {target.instrument_id: target for target in targets}
    targets_by_provider_symbol = {
        target.provider_symbol: target for target in targets
    }
    symbols = [target.provider_symbol for target in targets]
    with Session(engine) as session:
        service = PriceRefreshService(SqlAlchemyPriceBarRepository(session))
        plan = service.plan(
            universe,
            targets,
            full_start=full_start,
            end=end,
            mode=mode,
            already_refreshed=already_refreshed,
        )
    grouped_plan: dict[date, list[str]] = {}
    for instrument_id, start in plan.requested_starts.items():
        grouped_plan.setdefault(start, []).append(
            targets_by_id[instrument_id].provider_symbol
        )
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
                targets_by_provider_symbol=targets_by_provider_symbol,
                source="yfinance",
                fetched_at=fetched_at,
            )
    print(
        f"{universe}: stored={stored.stored_rows} rejected={stored.rejected_rows} "
        f"errors={len(errors)}",
        flush=True,
    )
    failed_symbols = {str(error["symbol"]) for error in errors}
    return {
        targets_by_provider_symbol[symbol].instrument_id
        for symbol in set(symbols) - failed_symbols
    }


def refresh_vn_market(
    engine: Engine,
    universe: str,
    full_start: date,
    end: date,
    delay: float,
    mode: str,
    *,
    already_refreshed: set[int] | None = None,
    provider: VietnamMarketProvider | None = None,
    allow_community_fallback: bool = False,
) -> set[int]:
    primary_provider = provider or create_vietnam_market_provider(
        require_sponsored=True
    )
    fallbacks = _community_fallbacks(allow_community_fallback)
    primary_name = _provider_name(primary_provider)
    instruments = _scope_instruments(engine, universe)
    targets, routes = _refresh_targets(engine, instruments)
    if {target.price_adapter for target in targets} != {"vnstock_data"}:
        raise RuntimeError(f"{universe} is not a vnstock_data equity universe")
    end = min(
        end,
        latest_completed_venue_session(
            datetime.now(timezone.utc), next(iter(routes.values())).schedule
        ),
    )
    targets_by_id = {target.instrument_id: target for target in targets}
    targets_by_provider_symbol = {
        target.provider_symbol: target for target in targets
    }
    symbols = [target.provider_symbol for target in targets]
    with Session(engine) as session:
        plan = PriceRefreshService(
            SqlAlchemyPriceBarRepository(session)
        ).plan(
            universe,
            targets,
            full_start=full_start,
            end=end,
            mode=mode,
            already_refreshed=already_refreshed,
        )
    start_by_symbol = {
        targets_by_id[instrument_id].provider_symbol: start
        for instrument_id, start in plan.requested_starts.items()
    }
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
            and checkpoint_manifest.get("source") == primary_name
            and checkpoint_manifest.get("community_fallback")
            == allow_community_fallback
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
            "source": primary_name,
            "community_fallback": allow_community_fallback,
        })
    )

    results: dict[str, VNFetchResult] = {}
    for index, symbol in enumerate(requested_symbols, start=1):
        if symbol in completed_symbols:
            continue
        result = _fetch_vn_history(
            primary_provider,
            symbol,
            start_by_symbol[symbol],
            end,
            community_fallbacks=fallbacks,
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
            instrument_id=targets_by_provider_symbol[symbol].instrument_id,
            price_basis=targets_by_provider_symbol[symbol].price_basis,
            attempted_through=end,
            returned_through=result.returned_through,
            outcome=result.outcome,
            primary_source=primary_name,
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
                        targets_by_provider_symbol=targets_by_provider_symbol,
                        source=str(source),
                        fetched_at=fetched_at,
                    )
                    stored_rows += stored.stored_rows
                    rejected_rows += stored.rejected_rows
            service.record_attempts(attempts)
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
        f"attempted_through={end.isoformat()} primary={primary_name} "
        f"community_fallback={allow_community_fallback}",
        flush=True,
    )
    if errors:
        raise RuntimeError(
            f"{universe} refresh failed for {len(errors)} symbols: {errors}"
        )
    return {target.instrument_id for target in targets}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--universe",
        required=True,
        help="Any PostgreSQL Universe code; routing comes from its Instrument metadata.",
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
    parser.add_argument(
        "--vn-delay",
        type=float,
        default=None,
        help=(
            "Seconds between sponsored VN requests. Defaults to the rate "
            "derived from VNSTOCK_REQUESTS_PER_MINUTE."
        ),
    )
    parser.add_argument(
        "--allow-community-fallback",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Allow explicit KBS then VCI community fallback after sponsor failure.",
    )
    parser.add_argument("--database-url", default=None)
    args = parser.parse_args()
    engine = create_db_engine(args.database_url)
    requests_per_minute = env_float(
        "VNSTOCK_REQUESTS_PER_MINUTE", DEFAULT_VN_REQUESTS_PER_MINUTE
    )
    if requests_per_minute <= 0:
        parser.error("VNSTOCK_REQUESTS_PER_MINUTE must be greater than zero")
    vn_delay = (
        args.vn_delay
        if args.vn_delay is not None
        else 60.0 / requests_per_minute
    )
    allow_community_fallback = (
        args.allow_community_fallback
        if args.allow_community_fallback is not None
        else env_bool("VNSTOCK_ALLOW_COMMUNITY_FALLBACK", False)
    )

    universes = (args.universe.upper(),)
    refreshed_by_adapter: dict[str, set[int]] = {}
    benchmarked_adapters: set[str] = set()
    for universe in universes:
        instruments = _scope_instruments(engine, universe)
        targets, routes = _refresh_targets(engine, instruments)
        adapters = {target.price_adapter for target in targets}
        if len(adapters) != 1:
            raise RuntimeError(f"{universe} does not use one price adapter")
        adapter = next(iter(adapters))
        route = next(iter(routes.values()))
        end = latest_completed_venue_session(datetime.now(timezone.utc), route.schedule)
        full_start = (
            route.full_history_start
            if args.calendar_days is None
            else end - timedelta(days=args.calendar_days)
        )
        already_refreshed = refreshed_by_adapter.setdefault(adapter, set())
        if adapter == "yfinance":
            if adapter not in benchmarked_adapters:
                refresh_benchmark("SPX", full_start, end, args.mode)
            already_refreshed |= refresh_us_market(
                engine,
                universe,
                full_start,
                end,
                args.mode,
                already_refreshed=already_refreshed,
            )
        elif adapter == "vnstock_data":
            if adapter not in benchmarked_adapters:
                refresh_benchmark("VN30", full_start, end, args.mode)
            already_refreshed |= refresh_vn_market(
                engine,
                universe,
                full_start,
                end,
                vn_delay,
                args.mode,
                already_refreshed=already_refreshed,
                allow_community_fallback=allow_community_fallback,
            )
        else:
            raise RuntimeError(
                f"Bulk equity refresh does not support adapter {adapter}"
            )
        benchmarked_adapters.add(adapter)


if __name__ == "__main__":
    main()
