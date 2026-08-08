"""Run a read-only sponsored-provider diagnostic against FPT by default."""
from __future__ import annotations

import argparse
from datetime import date, timedelta
import json
from typing import Any

import pandas as pd

from api.providers.vietnam_market import create_vietnam_market_provider


def _summary(frame: pd.DataFrame, date_column: str) -> dict[str, Any]:
    dates = pd.to_datetime(frame[date_column], errors="coerce").dropna()
    return {
        "rows": len(frame),
        "columns": list(frame.columns),
        "first_date": dates.min().date().isoformat() if not dates.empty else None,
        "last_date": dates.max().date().isoformat() if not dates.empty else None,
    }


def run_diagnostic(symbol: str, start: date, end: date) -> dict[str, Any]:
    provider = create_vietnam_market_provider(require_sponsored=True)
    ohlcv = provider.ohlcv(symbol, start, end)
    trades = provider.trade_history(symbol, start, end)
    metadata = ohlcv.metadata
    return {
        "authenticated": True,
        "package": metadata.package,
        "package_version": metadata.package_version,
        "access_mode": metadata.access_mode,
        "symbol": metadata.symbol,
        "requested_start": start.isoformat(),
        "requested_end": end.isoformat(),
        "ohlcv": _summary(ohlcv.frame, "time"),
        "trade_history": _summary(trades.frame, "trading_date"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="FPT")
    parser.add_argument("--end", type=date.fromisoformat, default=date.today())
    parser.add_argument("--start", type=date.fromisoformat)
    args = parser.parse_args()
    start = args.start or args.end - timedelta(days=7)
    result = run_diagnostic(args.symbol, start, args.end)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
