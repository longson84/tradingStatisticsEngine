"""Strategy renderers package — re-exports all public names for backward compatibility."""
from src.strategy.renderers.performance import render_performance_summary
from src.strategy.utils import build_bucket_breakdown, build_percentile_breakdown
from src.strategy.renderers.distributions import (
    _render_bucket_breakdown,
    render_distribution,
    _render_percentile_breakdown,
)
from src.strategy.monthly import (
    build_monthly_returns_df,
    build_monthly_stats_df,
    build_trade_entry_month_stats_df,
)
from src.strategy.renderers.monthly import render_monthly_returns_tables
from src.styling import style_monthly_stats_table, style_monthly_returns_table
from src.strategy.renderers.deterioration import render_deterioration_section

__all__ = [
    "render_performance_summary",
    "build_bucket_breakdown",
    "build_percentile_breakdown",
    "_render_bucket_breakdown",
    "render_distribution",
    "_render_percentile_breakdown",
    "build_monthly_returns_df",
    "build_monthly_stats_df",
    "build_trade_entry_month_stats_df",
    "render_monthly_returns_tables",
    "style_monthly_stats_table",
    "style_monthly_returns_table",
    "render_deterioration_section",
]
