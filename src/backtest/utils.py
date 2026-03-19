"""General-purpose data processing utilities for backtest analysis."""
from typing import Sequence

import numpy as np

from src.shared.constants import SUMMARY_PERCENTILES
from src.shared.fmt import fmt_pct


def build_percentile_breakdown(
    values: list[float],
    label: str,
    percentiles: Sequence[int],
) -> list[dict[str, str]]:
    """Build percentile breakdown rows for display tables (includes Mean and Std Dev)."""
    rows = [{"Percentile": f"P{p}", label: fmt_pct(np.percentile(values, p))} for p in percentiles]
    rows.append({"Percentile": "Mean", label: fmt_pct(np.mean(values))})
    rows.append({"Percentile": "Std Dev", label: fmt_pct(np.std(values, ddof=1))})
    return rows


def compute_summary_percentiles(
    values: list[float],
    percentiles: Sequence[int] = SUMMARY_PERCENTILES,
) -> dict[str, float | None]:
    """Percentile dict for summary tables."""
    if not values:
        return {f"P{n} %": None for n in percentiles}
    return {f"P{n} %": round(float(np.percentile(values, n)), 2) for n in percentiles}


def build_bucket_breakdown(
    values: list[float],
    metric_label: str,
    buckets: Sequence[tuple[str, float, float]],
) -> list[dict]:
    """Build bucket count rows for display tables."""
    total = len(values)
    rows = []
    for label, lo, hi in buckets:
        subset = [v for v in values if lo < v <= hi] if hi != float("inf") else [v for v in values if v > lo]
        count = len(subset)
        rows.append({
            "Range": label,
            "Count": count,
            "% of Total": fmt_pct(count / total * 100) if total else "0.00%",
            f"Avg {metric_label}": fmt_pct(np.mean(subset)) if subset else "—",
        })
    return rows
