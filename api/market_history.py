"""Persistent local OHLCV cache used by market-wide analysis endpoints."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from trading_engine.types import DataLoadError, PriceFrame


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE_DIR = PROJECT_ROOT / ".cache" / "market_history"
SUPPORTED_UNIVERSES = {"US100", "US2000", "US500", "VN30", "VN100"}
PRICE_COLUMNS = ["open", "high", "low", "close", "volume"]


def load_cached_market_history(
    universe: str,
    *,
    cache_dir: Path = DEFAULT_CACHE_DIR,
) -> tuple[dict[str, PriceFrame], dict[str, Any]]:
    """Load one universe from its long-form CSV cache and JSON manifest."""
    normalized = universe.upper()
    if normalized not in SUPPORTED_UNIVERSES:
        raise DataLoadError(f"Unsupported cached universe: {universe!r}")

    csv_path = cache_dir / f"{normalized.lower()}.csv"
    manifest_path = cache_dir / f"{normalized.lower()}.json"
    if not csv_path.exists() or not manifest_path.exists():
        raise DataLoadError(
            f"History cache for {normalized} is missing. Run "
            f"`uv run python -m scripts.refresh_market_history --market {normalized.lower()}`."
        )

    try:
        manifest = json.loads(manifest_path.read_text())
        raw = pd.read_csv(csv_path, parse_dates=["date"])
    except (json.JSONDecodeError, ValueError, OSError) as exc:
        raise DataLoadError(f"Invalid history cache for {normalized}: {exc}") from exc

    required = {"symbol", "date", "open", "high", "low", "close"}
    missing = required - set(raw.columns)
    if missing:
        raise DataLoadError(
            f"History cache for {normalized} is missing columns: {sorted(missing)}"
        )

    prices: dict[str, PriceFrame] = {}
    source = str(manifest.get("source", "cache"))
    for symbol, rows in raw.groupby("symbol", sort=True):
        frame = rows.sort_values("date").set_index("date")
        frame.index = pd.DatetimeIndex(frame.index).normalize()
        frame.index.name = "date"
        keep = [column for column in PRICE_COLUMNS if column in frame.columns]
        prices[str(symbol)] = PriceFrame(
            symbol=str(symbol),
            data=frame[keep].astype(float),
            source=source,
        )

    if not prices:
        raise DataLoadError(f"History cache for {normalized} contains no symbols")
    return prices, manifest


def load_cached_market_symbol(
    universe: str,
    symbol: str,
    *,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    chunksize: int = 100_000,
) -> tuple[PriceFrame, dict[str, Any]]:
    """Load one symbol from a universe cache without materializing every ticker."""
    normalized_universe = universe.upper()
    normalized_symbol = symbol.upper().strip()
    if normalized_universe not in SUPPORTED_UNIVERSES:
        raise DataLoadError(f"Unsupported cached universe: {universe!r}")
    if not normalized_symbol:
        raise DataLoadError("A symbol is required")

    csv_path = cache_dir / f"{normalized_universe.lower()}.csv"
    manifest_path = cache_dir / f"{normalized_universe.lower()}.json"
    if not csv_path.exists() or not manifest_path.exists():
        raise DataLoadError(
            f"History cache for {normalized_universe} is missing. Run "
            f"`uv run python -m scripts.refresh_market_history --market "
            f"{normalized_universe.lower()}`."
        )

    try:
        manifest = json.loads(manifest_path.read_text())
        matches = []
        for chunk in pd.read_csv(csv_path, parse_dates=["date"], chunksize=chunksize):
            required = {"symbol", "date", "open", "high", "low", "close"}
            missing = required - set(chunk.columns)
            if missing:
                raise DataLoadError(
                    f"History cache for {normalized_universe} is missing columns: "
                    f"{sorted(missing)}"
                )
            selected = chunk[
                chunk["symbol"].astype(str).str.upper() == normalized_symbol
            ]
            if not selected.empty:
                matches.append(selected)
    except DataLoadError:
        raise
    except (json.JSONDecodeError, ValueError, OSError) as exc:
        raise DataLoadError(
            f"Invalid history cache for {normalized_universe}: {exc}"
        ) from exc

    if not matches:
        raise DataLoadError(
            f"{normalized_symbol} is not present in the {normalized_universe} history cache"
        )

    frame = (
        pd.concat(matches, ignore_index=True)
        .sort_values("date")
        .drop_duplicates("date", keep="last")
        .set_index("date")
    )
    frame.index = pd.DatetimeIndex(frame.index).normalize()
    frame.index.name = "date"
    keep = [column for column in PRICE_COLUMNS if column in frame.columns]
    return PriceFrame(
        symbol=normalized_symbol,
        data=frame[keep].astype(float),
        source=str(manifest.get("source", "cache")),
    ), manifest


def save_market_history(
    universe: str,
    data: pd.DataFrame,
    manifest: dict[str, Any],
    *,
    cache_dir: Path = DEFAULT_CACHE_DIR,
) -> None:
    """Atomically replace one universe's local CSV cache and manifest."""
    normalized = universe.upper()
    if normalized not in SUPPORTED_UNIVERSES:
        raise ValueError(f"Unsupported cached universe: {universe!r}")

    cache_dir.mkdir(parents=True, exist_ok=True)
    csv_path = cache_dir / f"{normalized.lower()}.csv"
    manifest_path = cache_dir / f"{normalized.lower()}.json"
    csv_tmp = csv_path.with_suffix(".csv.tmp")
    manifest_tmp = manifest_path.with_suffix(".json.tmp")

    ordered = data.sort_values(["symbol", "date"]).drop_duplicates(
        ["symbol", "date"],
        keep="last",
    )
    ordered.to_csv(csv_tmp, index=False)
    manifest_tmp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    csv_tmp.replace(csv_path)
    manifest_tmp.replace(manifest_path)
