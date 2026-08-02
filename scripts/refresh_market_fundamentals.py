"""Refresh persistent point-in-time fundamentals for one or all universes."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import time

from api.fundamentals_cache import (
    cache_paths,
    refresh_symbol_fundamentals,
    universe_symbols,
)


REUSE_WINDOW = timedelta(hours=12)


def _recently_refreshed(symbol: str, market: str, started_at: datetime) -> bool:
    _, manifest_path = cache_paths(symbol, market)
    if not manifest_path.exists():
        return False
    try:
        manifest = json.loads(manifest_path.read_text())
        fetched_at = datetime.fromisoformat(str(manifest["fetched_at"]))
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=timezone.utc)
    except (KeyError, ValueError, OSError, json.JSONDecodeError):
        return False
    return started_at - fetched_at <= REUSE_WINDOW


def refresh_universe(universe: str, *, delay: float) -> None:
    symbols = universe_symbols(universe)
    market = "VN" if universe.startswith("VN") else "US"
    started_at = datetime.now(timezone.utc)
    to_fetch = [
        symbol for symbol in symbols
        if not _recently_refreshed(symbol, market, started_at)
    ]
    reused = len(symbols) - len(to_fetch)
    print(
        f"{universe}: reusing {reused}/{len(symbols)} recent fundamental caches; "
        f"downloading {len(to_fetch)}",
        flush=True,
    )
    errors: list[dict[str, str]] = []
    for index, symbol in enumerate(to_fetch, start=1):
        try:
            refresh_symbol_fundamentals(symbol, market, fetched_at=started_at)
        except Exception as exc:
            errors.append({"symbol": symbol, "error": str(exc)})
        completed = reused + index
        print(
            f"{universe}: {completed}/{len(symbols)} errors={len(errors)}",
            flush=True,
        )
        if index < len(to_fetch):
            time.sleep(delay)
    if to_fetch and len(errors) == len(to_fetch):
        raise RuntimeError(f"No fundamentals could be refreshed: {errors[:5]}")
    print(
        f"{universe}: fundamentals complete; refreshed={len(to_fetch) - len(errors)} "
        f"reused={reused} errors={len(errors)}",
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--market",
        choices=("all", "us2000", "us500", "us100", "vn100", "vn30"),
        default="all",
    )
    parser.add_argument("--us-delay", type=float, default=0.25)
    parser.add_argument("--vn-delay", type=float, default=4.1)
    args = parser.parse_args()
    order = (
        ("US2000", args.us_delay),
        ("US500", args.us_delay),
        ("US100", args.us_delay),
        ("VN100", args.vn_delay),
        ("VN30", args.vn_delay),
    )
    if args.market == "all":
        for universe, delay in order:
            refresh_universe(universe, delay=delay)
        return
    universe = args.market.upper()
    delay = args.vn_delay if universe.startswith("VN") else args.us_delay
    refresh_universe(universe, delay=delay)


if __name__ == "__main__":
    main()
