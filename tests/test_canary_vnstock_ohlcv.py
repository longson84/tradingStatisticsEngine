from __future__ import annotations

import pandas as pd

from scripts.canary_vnstock_ohlcv import compare_frames


def _frame(dates, closes, volumes):
    return pd.DataFrame({
        "date": pd.to_datetime(dates),
        "open": closes,
        "high": closes,
        "low": closes,
        "close": closes,
        "volume": volumes,
    })


def test_identical_history_with_earlier_sponsored_date_is_safe():
    sponsored = _frame(
        ["2026-08-05", "2026-08-06", "2026-08-07"],
        [70.3, 70.7, 70.8],
        [3, 4, 5],
    )
    stored = _frame(
        ["2026-08-06", "2026-08-07"],
        [70.7, 70.8],
        [4, 5],
    )

    result = compare_frames(sponsored, stored)

    assert result["safe_to_write"] is True
    assert result["new_provider_dates"] == 1
    assert result["price_mismatch_rows"] == 0


def test_provider_price_disagreement_blocks_write():
    sponsored = _frame(["2026-08-07"], [70.8], [5])
    stored = _frame(["2026-08-07"], [71.8], [5])

    result = compare_frames(sponsored, stored)

    assert result["safe_to_write"] is False
    assert result["price_mismatch_rows"] == 1


def test_missing_stored_session_blocks_write():
    sponsored = _frame(["2026-08-07"], [70.8], [5])
    stored = _frame(
        ["2026-08-06", "2026-08-07"],
        [70.7, 70.8],
        [4, 5],
    )

    result = compare_frames(sponsored, stored)

    assert result["safe_to_write"] is False
    assert result["missing_from_provider"] == 1
