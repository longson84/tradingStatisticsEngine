"""System-wide constants for the trading engine.

These are the defaults used across all analyses. API consumers can override
them per-request; notebooks can override them per-cell.
"""

# Percentile zones for Rarity Analysis.
# Ordered ascending; each zone is a left-tail threshold (factor ≤ P_k threshold).
# Add or remove zones here to change the default breakdown globally.
DEFAULT_RARITY_ZONES: list[int] = [1, 5, 10, 15, 20, 25, 30, 40, 50]

# Quick Recovery window (trading sessions).
# An entry is "quick recovery" if the factor exits the zone within this many sessions.
DEFAULT_QR_DAYS: int = 5

# MAE percentile levels reported in ZoneStats.
# Each value becomes a column in the Rarity Analysis summary table.
DEFAULT_MAE_PERCENTILES: list[int] = [80, 85, 90, 95, 98]
