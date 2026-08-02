"""Persistent local histories for market benchmarks used by indicators."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from api.market_history import PROJECT_ROOT
from trading_engine.types import DataLoadError, PriceFrame


Benchmark = Literal["VN30", "SPX"]
DEFAULT_BENCHMARK_DIR = PROJECT_ROOT / ".cache" / "benchmark_history"
SUPPORTED_BENCHMARKS = {"VN30", "SPX"}


def load_cached_benchmark(
    benchmark: str,
    *,
    cache_dir: Path = DEFAULT_BENCHMARK_DIR,
) -> tuple[PriceFrame, dict[str, Any]]:
    normalized = benchmark.upper()
    if normalized not in SUPPORTED_BENCHMARKS:
        raise DataLoadError(f"Unsupported benchmark: {benchmark!r}")
    csv_path = cache_dir / f"{normalized.lower()}.csv"
    manifest_path = cache_dir / f"{normalized.lower()}.json"
    if not csv_path.exists() or not manifest_path.exists():
        raise DataLoadError(
            f"Benchmark cache for {normalized} is missing. Refresh prices in Market Data."
        )
    try:
        manifest = json.loads(manifest_path.read_text())
        frame = pd.read_csv(csv_path, parse_dates=["date"]).set_index("date")
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        raise DataLoadError(f"Invalid benchmark cache for {normalized}: {exc}") from exc
    required = {"open", "high", "low", "close"}
    if missing := required - set(frame.columns):
        raise DataLoadError(
            f"Benchmark cache for {normalized} is missing columns: {sorted(missing)}"
        )
    frame.index = pd.DatetimeIndex(frame.index).normalize()
    frame.index.name = "date"
    keep = [column for column in ("open", "high", "low", "close", "volume") if column in frame]
    return PriceFrame(
        symbol=normalized,
        data=frame[keep].astype(float).sort_index(),
        source=str(manifest.get("source", "cache")),
    ), manifest


def save_benchmark_history(
    benchmark: str,
    data: pd.DataFrame,
    manifest: dict[str, Any],
    *,
    cache_dir: Path = DEFAULT_BENCHMARK_DIR,
) -> None:
    normalized = benchmark.upper()
    if normalized not in SUPPORTED_BENCHMARKS:
        raise ValueError(f"Unsupported benchmark: {benchmark!r}")
    cache_dir.mkdir(parents=True, exist_ok=True)
    csv_path = cache_dir / f"{normalized.lower()}.csv"
    manifest_path = cache_dir / f"{normalized.lower()}.json"
    csv_tmp = csv_path.with_suffix(".csv.tmp")
    manifest_tmp = manifest_path.with_suffix(".json.tmp")
    data.sort_values("date").drop_duplicates("date", keep="last").to_csv(csv_tmp, index=False)
    manifest_tmp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    csv_tmp.replace(csv_path)
    manifest_tmp.replace(manifest_path)
