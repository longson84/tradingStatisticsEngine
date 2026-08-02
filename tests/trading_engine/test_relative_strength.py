from __future__ import annotations

import pandas as pd
import pytest

from trading_engine.factors import normalized_relative_strength


def test_relative_strength_is_rebased_to_latest_stock_close():
    dates = pd.to_datetime(["2026-01-02", "2026-01-05", "2026-01-06"])
    close = pd.Series([100.0, 120.0, 132.0], index=dates)
    benchmark = pd.Series([1000.0, 1100.0, 1100.0], index=dates)

    result = normalized_relative_strength(close, benchmark)

    assert result.iloc[-1] == pytest.approx(132.0)
    assert result.iloc[0] == pytest.approx(110.0)
    assert result.iloc[1] == pytest.approx(120.0)


def test_relative_strength_forward_fills_only_past_benchmark_sessions():
    dates = pd.to_datetime(["2026-01-02", "2026-01-05", "2026-01-06"])
    close = pd.Series([100.0, 105.0, 110.0], index=dates)
    benchmark = pd.Series(
        [1000.0, 1100.0],
        index=pd.to_datetime(["2026-01-05", "2026-01-06"]),
    )

    result = normalized_relative_strength(close, benchmark)

    assert pd.isna(result.iloc[0])
    assert result.iloc[-1] == pytest.approx(110.0)
