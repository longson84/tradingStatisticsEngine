"""Persistent local price-history cache for individual symbols."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from trading_engine.types import DataLoadError, PriceFrame


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SYMBOL_HISTORY_DIR = PROJECT_ROOT / ".cache" / "symbol_history"
PRICE_COLUMNS = ["open", "high", "low", "close", "volume"]


def load_cached_symbol_history(
    symbol: str,
    *,
    cache_dir: Path = DEFAULT_SYMBOL_HISTORY_DIR,
) -> tuple[PriceFrame, dict[str, Any]]:
    """Load one symbol's full available history and cache manifest."""
    normalized = symbol.upper().strip()
    csv_path = cache_dir / f"{normalized.lower()}.csv"
    manifest_path = cache_dir / f"{normalized.lower()}.json"
    if not csv_path.exists() or not manifest_path.exists():
        raise DataLoadError(
            f"Full history cache for {normalized} is missing. Run "
            f"`uv run python -m scripts.refresh_symbol_history {normalized}`."
        )

    try:
        manifest = json.loads(manifest_path.read_text())
        raw = pd.read_csv(csv_path, parse_dates=["date"])
    except (json.JSONDecodeError, ValueError, OSError) as exc:
        raise DataLoadError(f"Invalid full history cache for {normalized}: {exc}") from exc

    required = {"date", "open", "high", "low", "close"}
    missing = required - set(raw.columns)
    if missing:
        raise DataLoadError(
            f"Full history cache for {normalized} is missing columns: {sorted(missing)}"
        )

    frame = raw.sort_values("date").drop_duplicates("date", keep="last").set_index("date")
    frame.index = pd.DatetimeIndex(frame.index).normalize()
    frame.index.name = "date"
    keep = [column for column in PRICE_COLUMNS if column in frame.columns]
    if frame.empty:
        raise DataLoadError(f"Full history cache for {normalized} contains no rows")
    return (
        PriceFrame(
            symbol=normalized,
            data=frame[keep].astype(float),
            source=str(manifest.get("source", "cache")),
        ),
        manifest,
    )


def save_symbol_history(
    symbol: str,
    data: pd.DataFrame,
    manifest: dict[str, Any],
    *,
    cache_dir: Path = DEFAULT_SYMBOL_HISTORY_DIR,
) -> None:
    """Atomically replace one symbol's full-history cache and manifest."""
    normalized = symbol.upper().strip()
    cache_dir.mkdir(parents=True, exist_ok=True)
    csv_path = cache_dir / f"{normalized.lower()}.csv"
    manifest_path = cache_dir / f"{normalized.lower()}.json"
    csv_tmp = csv_path.with_suffix(".csv.tmp")
    manifest_tmp = manifest_path.with_suffix(".json.tmp")

    ordered = data.sort_values("date").drop_duplicates("date", keep="last")
    ordered.to_csv(csv_tmp, index=False)
    manifest_tmp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    csv_tmp.replace(csv_path)
    manifest_tmp.replace(manifest_path)
