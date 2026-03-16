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
