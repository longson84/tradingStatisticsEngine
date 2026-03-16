# Shared infrastructure constants (used across domains)
HISTORICAL_DATA_START_DATE = '1980-01-01'

# Display formatting — single source of truth for the whole app
DATE_FORMAT_DISPLAY = '%d/%m/%y'   # e.g. 16/10/08


def fmt_price(v: float) -> str:
    """Format a price: 60,000  (no decimal, thousands separator)."""
    return f"{v:,.0f}"


def fmt_pct(v: float) -> str:
    """Format a percentage: 12.34%  (2 decimals, thousands separator on integer part)."""
    return f"{v:,.2f}%"


def fmt_pct_signed(v: float) -> str:
    """Format a percentage with explicit sign: +12.34% or -5.67%."""
    return f"{v:+,.2f}%"


# ---------------------------------------------------------------------------
# Cell / row colour styles — single source of truth for Styler usage
# ---------------------------------------------------------------------------

# Positive value (gain): light green background, dark green text
COLOR_POSITIVE = "background-color: #bbf7d0; color: #14532d; font-weight: bold"
# Negative value (loss): light red background, dark red text
COLOR_NEGATIVE = "background-color: #fecaca; color: #7f1d1d; font-weight: bold"
# Active / open state (open trade, unrecovered event, current stats zone): gold
COLOR_ACTIVE = "background-color: #FFD700; color: black; font-weight: bold"
# Primary group row (e.g. Lv-0 event tree rows): teal-green
COLOR_GROUP = "background-color: #3aa56c; color: black; font-weight: bold"


def style_positive_negative(value: float | None, threshold: float = 0.0) -> str:
    """Return CSS for a numeric value: positive → green, negative → red, within ±threshold → ''.

    Args:
        value: the numeric value to evaluate.
        threshold: values whose abs() is <= this are considered insignificant (no colour).
    """
    if value is None or abs(value) <= threshold:
        return ""
    return COLOR_POSITIVE if value > 0 else COLOR_NEGATIVE
