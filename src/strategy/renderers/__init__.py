"""Strategy renderers package — re-exports all public names for backward compatibility."""
from src.strategy.renderers.performance import render_performance_summary
from src.strategy.renderers.distributions import (
    render_nonneg_distribution,
    render_return_distribution,
)
from src.strategy.renderers.monthly import (
    build_monthly_returns_df,
    build_monthly_stats_df,
    build_trade_entry_month_stats_df,
    render_monthly_returns_tables,
    style_monthly_stats_df,
    style_monthly_table,
)
from src.strategy.renderers.deterioration import render_deterioration_section

__all__ = [
    "render_performance_summary",
    "render_nonneg_distribution",
    "render_return_distribution",
    "build_monthly_returns_df",
    "build_monthly_stats_df",
    "build_trade_entry_month_stats_df",
    "render_monthly_returns_tables",
    "style_monthly_stats_df",
    "style_monthly_table",
    "render_deterioration_section",
]
