from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from api.fundamental_provider import normalize_fundamentals
from scripts.canary_vnstock_fundamentals import snapshot_errors


def _frame() -> pd.DataFrame:
    return normalize_fundamentals(pd.DataFrame({
        "effective_date": ["2026-10-19"],
        "period_end": ["2026-09-30"],
        "period": ["2026-Q3"],
        "eps_ttm": [5.25],
        "reported_pe": [12.4],
    }))


def test_canary_accepts_one_current_acquisition_dated_snapshot():
    assert snapshot_errors(
        _frame(), observed_at=datetime(2026, 10, 18, 5, tzinfo=UTC)
    ) == []


def test_canary_rejects_multiple_backfilled_snapshots():
    frame = pd.concat([_frame(), _frame()], ignore_index=True)

    assert snapshot_errors(
        frame, observed_at=datetime(2026, 10, 18, 5, tzinfo=UTC)
    ) == ["expected one current snapshot, received 2"]


def test_canary_rejects_historical_effective_date():
    frame = _frame()
    frame.loc[0, "effective_date"] = pd.Timestamp("2026-04-29")

    assert snapshot_errors(
        frame, observed_at=datetime(2026, 10, 18, 5, tzinfo=UTC)
    ) == ["effective_date is not the day after acquisition"]
