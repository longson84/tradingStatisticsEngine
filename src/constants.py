# Shared infrastructure constants (used across domains)
HISTORICAL_DATA_START_DATE = '1980-01-01'
INITIAL_CAPITAL = 1000.0

# ---------------------------------------------------------------------------
# yfinance ticker presets — add/edit groups here
# ---------------------------------------------------------------------------
YFINANCE_PRESETS: dict[str, list[str]] = {
    "Crypto": ["BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD"],
    "Mag7":   ["MSFT", "AAPL", "TSLA", "NVDA", "META", "GOOGL", "NFLX"],
}

# Display formatting
DATE_FORMAT_DISPLAY = '%d/%m/%y'   # e.g. 16/10/08

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

# Plotly trace colours — use these for chart lines/markers so they stay in sync
# with the table colour scheme (same green/red family, adapted for dark backgrounds).
PLOTLY_POSITIVE = "#4ADE80"
PLOTLY_NEGATIVE = "#F87171"

# ---------------------------------------------------------------------------
# Distribution bucket definitions
# ---------------------------------------------------------------------------

RETURN_BUCKETS: list[tuple[str, float, float]] = [
    ("< -20%",      float("-inf"), -20),
    ("-20 → -10%",         -20,   -10),
    ("-10 → -5%",          -10,    -5),
    ("-5 → 0%",             -5,     0),
    ("0 → 5%",               0,     5),
    ("5 → 10%",              5,    10),
    ("10 → 20%",            10,    20),
    ("> 20%",               20, float("inf")),
]

NONNEG_BUCKETS: list[tuple[str, float, float]] = [
    ("0 → 5%",      0,   5),
    ("5 → 10%",     5,  10),
    ("10 → 20%",   10,  20),
    ("20 → 30%",   20,  30),
    ("30 → 50%",   30,  50),
    ("50 → 100%",  50, 100),
    ("> 100%",    100, float("inf")),
]

# ---------------------------------------------------------------------------
# Percentile configuration
# ---------------------------------------------------------------------------

SUMMARY_PERCENTILES: tuple[int, ...] = (90, 70, 50, 30, 10)

ANNUAL_PERCENTILES = [90, 80, 70, 60, 50, 40, 30, 20, 10]

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

