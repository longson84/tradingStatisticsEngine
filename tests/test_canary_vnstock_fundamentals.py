from __future__ import annotations

import pandas as pd

from api.fundamental_provider import normalize_fundamentals
from scripts.canary_vnstock_fundamentals import latest_value_changes, parity_errors


def _frame() -> pd.DataFrame:
    return normalize_fundamentals(pd.DataFrame({
        "effective_date": ["2026-04-29"],
        "period_end": ["2026-03-31"],
        "period": ["2026-Q1"],
        "eps_ttm": [5.25],
        "reported_pe": [12.4],
    }))


def test_canary_accepts_equivalent_provider_frame():
    assert parity_errors(_frame(), _frame().copy()) == []


def test_canary_rejects_point_in_time_drift():
    fetched = _frame()
    fetched.loc[0, "effective_date"] = pd.Timestamp("2026-04-28")

    assert parity_errors(_frame(), fetched) == [
        "identity differs in effective_date"
    ]


def test_canary_allows_and_reports_latest_provider_revision():
    existing = pd.concat([_frame(), _frame().assign(
        effective_date=pd.Timestamp("2026-07-29"),
        period_end=pd.Timestamp("2026-06-30"),
        period="2026-Q2",
    )], ignore_index=True)
    fetched = existing.copy()
    fetched.loc[1, "reported_pe"] = 13.1

    assert parity_errors(existing, fetched) == []
    assert latest_value_changes(existing, fetched) == ["reported_pe"]
