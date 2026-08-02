from __future__ import annotations

import pandas as pd

from api.benchmark_history import load_cached_benchmark, save_benchmark_history


def test_benchmark_cache_round_trip(tmp_path):
    data = pd.DataFrame({
        "date": pd.to_datetime(["2026-07-30", "2026-07-31"]),
        "open": [1000.0, 1010.0],
        "high": [1020.0, 1030.0],
        "low": [990.0, 1000.0],
        "close": [1010.0, 1020.0],
        "volume": [1_000_000.0, 1_100_000.0],
    })
    manifest = {
        "benchmark": "VN30",
        "source": "vnstock-vci",
        "price_basis": "provider OHLC (adjustment unspecified)",
    }

    save_benchmark_history("VN30", data, manifest, cache_dir=tmp_path)
    prices, loaded_manifest = load_cached_benchmark("vn30", cache_dir=tmp_path)

    assert prices.symbol == "VN30"
    assert prices.data["close"].tolist() == [1010.0, 1020.0]
    assert loaded_manifest == manifest
