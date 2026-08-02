"""Refresh the full available KBS history for one Vietnam stock symbol."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone

import pandas as pd

from api.symbol_history import save_symbol_history


def refresh_symbol_history(symbol: str, end: date) -> None:
    from vnstock import Quote

    normalized = symbol.upper().strip()
    raw = Quote(symbol=normalized, source="KBS").history(
        start="2000-01-01",
        end=end.isoformat(),
        interval="1D",
    )
    if raw is None or raw.empty:
        raise RuntimeError(f"KBS returned no history for {normalized}")

    data = raw.rename(columns={"time": "date"}).copy()
    data["date"] = pd.to_datetime(data["date"]).dt.normalize()
    columns = ["date", "open", "high", "low", "close", "volume"]
    data = data[[column for column in columns if column in data.columns]].dropna(
        subset=["open", "high", "low", "close"]
    )
    manifest = {
        "symbol": normalized,
        "fetched_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "first_date": str(data["date"].min().date()),
        "last_date": str(data["date"].max().date()),
        "row_count": len(data),
        "source": "vnstock-kbs",
        "price_basis": "provider OHLC (adjustment unspecified)",
    }
    save_symbol_history(normalized, data, manifest)
    print(
        f"{normalized}: cached {len(data)} sessions from "
        f"{manifest['first_date']} through {manifest['last_date']}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("symbol")
    parser.add_argument("--end", type=date.fromisoformat, default=date.today())
    args = parser.parse_args()
    refresh_symbol_history(args.symbol, args.end)


if __name__ == "__main__":
    main()
