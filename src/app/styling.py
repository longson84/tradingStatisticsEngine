"""Cell / row CSS styling utilities — single source of truth for Styler usage."""
import pandas as pd

from src.shared.constants import ANNUAL_PERCENTILES, COLOR_NEGATIVE, COLOR_POSITIVE, MONTHS


def style_capture(val: str) -> str:
    if not isinstance(val, str) or val in ("", "—"):
        return ""
    try:
        return COLOR_POSITIVE if float(val.replace("×", "")) > 1 else COLOR_NEGATIVE
    except ValueError:
        return ""


def style_positive_negative(value: float | None, threshold: float = 0.0) -> str:
    if value is None or abs(value) <= threshold:
        return ""
    return COLOR_POSITIVE if value > 0 else COLOR_NEGATIVE


def style_pct_cell(val) -> str:
    if not isinstance(val, str) or val in ("", "—"):
        return ""
    try:
        numeric = float(val.replace(",", "").replace("%", ""))
    except ValueError:
        return ""
    if numeric > 0:
        return COLOR_POSITIVE
    elif numeric < 0:
        return COLOR_NEGATIVE
    return ""


def style_monthly_returns_table(df: pd.DataFrame) -> "pd.io.formats.style.Styler":
    color_cols = [c for c in MONTHS + ["Annual"] if c in df.columns]
    return df.style.applymap(style_pct_cell, subset=color_cols)


def style_monthly_stats_table(df: pd.DataFrame) -> "pd.io.formats.style.Styler":
    color_cols = [f"P{p}" for p in ANNUAL_PERCENTILES if f"P{p}" in df.columns]
    return df.style.applymap(style_pct_cell, subset=color_cols)
