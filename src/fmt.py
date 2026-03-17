"""Display formatting utilities — single source of truth for the whole app."""
from collections.abc import Sequence

import numpy as np


def fmt_price(v: float) -> str:
    """Format a price: 60,000  (no decimal, thousands separator)."""
    return f"{v:,.0f}"


def fmt_capture(v: float | None) -> str:
    """Format a capture ratio: 1.23×  (2 decimals, × suffix). Returns '—' for None."""
    if v is None:
        return "—"
    return f"{v:.2f}×"


def fmt_equity(v: float) -> str:
    """Format an equity value: 1,234  (no decimal, thousands separator, no $ sign)."""
    return f"{v:,.0f}"


def fmt_pct(v: float) -> str:
    """Format a percentage: 12.34%  (2 decimals, thousands separator on integer part)."""
    return f"{v:,.2f}%"


def fmt_pct_signed(v: float) -> str:
    """Format a percentage with explicit sign: +12.34% or -5.67%."""
    return f"{v:+,.2f}%"


def format_percentile_columns(
    values: list[float],
    percentiles: Sequence[int],
) -> dict[str, str]:
    """Percentile dict with ``fmt_pct`` formatting.

    Keys: ``"P{n}"``; values: formatted percentage strings or ``"—"`` when empty.
    """
    if not values:
        return {f"P{n}": "—" for n in percentiles}
    return {f"P{n}": fmt_pct(float(np.percentile(values, n))) for n in percentiles}
