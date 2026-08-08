from __future__ import annotations

from datetime import date

import pandas as pd

from api.providers.vietnam_market import (
    VietnamProviderMetadata,
    VietnamProviderResult,
)
from api.providers.vietnam_price_loader import VietnamPriceLoader


class Provider:
    def ohlcv(self, symbol, start, end, *, interval="1D"):
        return VietnamProviderResult(
            frame=pd.DataFrame({
                "time": pd.to_datetime(["2026-08-07", "2026-08-08"]),
                "open": [71.1, 70.8],
                "high": [71.7, 71.0],
                "low": [70.3, 70.0],
                "close": [70.8, 70.5],
                "volume": [4_301_800, 1_000],
            }),
            metadata=VietnamProviderMetadata(
                package="vnstock_data",
                package_version="3.2.7",
                access_mode="sponsored",
                upstream_source="VCI",
                method="ohlcv",
                symbol=symbol.upper(),
                requested_start=start,
                requested_end=end,
            ),
        )

    def trade_history(self, symbol, start, end):
        raise AssertionError("not used")


def test_loader_normalizes_sponsored_data_and_keeps_end_exclusive():
    result = VietnamPriceLoader(Provider()).load(
        "fpt", date(2026, 8, 1), date(2026, 8, 8)
    )

    assert result.symbol == "FPT"
    assert result.source == "vnstock-data-3.2.7-vci"
    assert result.data.index.date.tolist() == [date(2026, 8, 7)]
    assert result.data.loc["2026-08-07", "close"] == 70.8
