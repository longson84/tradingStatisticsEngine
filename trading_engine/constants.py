"""System-wide constants for the trading engine.

These are the defaults used across all analyses. API consumers can override
them per-request; notebooks can override them per-cell.
"""

# Percentile zones for Rarity Analysis.
# Ordered ascending; each zone is a left-tail threshold (factor ≤ P_k threshold).
# Add or remove zones here to change the default breakdown globally.
DEFAULT_RARITY_ZONES: list[int] = [1, 5, 10, 15, 20, 25, 30]

# Quick Recovery window (trading sessions).
# An entry is "quick recovery" if its configured recovery completes within this many sessions.
DEFAULT_QR_DAYS: int = 5

# Worst-tail MAE percentile levels reported in ZoneStats.
# MAE is a positive drawdown magnitude, so P5 means the 95th percentile
# threshold: only the worst 5% of non-quick-recovery entries had larger MAE.
DEFAULT_MAE_PERCENTILES: list[int] = [5, 10, 15, 20, 25, 50]
