"""Closed VCI daily trade-history contract and approved activity fields."""
from __future__ import annotations


TRADE_STATISTIC_SCHEMA_VERSION = 1

TRADE_HISTORY_PROVIDER_COLUMNS = (
    "trading_date", "end_trading_date", "market_cap", "total_shares",
    "ceiling_price", "floor_price", "reference_price", "open", "close",
    "match_price", "price_change", "percent_price_change", "high", "low",
    "average_price", "average_price_adjusted", "matched_volume",
    "matched_value", "deal_volume", "deal_value", "total_volume",
    "total_value", "total_buy_trade", "total_buy_trade_volume",
    "total_sell_trade", "total_sell_trade_volume", "reference_price_adjusted",
    "open_price_adjusted", "close_price_adjusted", "price_change_adjusted",
    "percent_price_change_adjusted", "highest_price_adjusted",
    "lowest_price_adjusted", "total_net_trade_volume",
    "total_buy_unmatched_volume", "total_sell_unmatched_volume",
    "price_change_value", "average_buy_trade_volume", "average_sell_trade_volume",
)

# Numeric activity columns only. Instrument identity and fetch provenance are
# supplied by the persistence boundary; raw and adjusted prices stay outside it.
TRADE_STATISTIC_STORAGE_COLUMNS = (
    "market_cap", "total_shares", "matched_volume", "matched_value",
    "deal_volume", "deal_value", "total_volume", "total_value",
    "total_buy_trade", "total_buy_trade_volume", "total_sell_trade",
    "total_sell_trade_volume", "total_net_trade_volume",
    "total_buy_unmatched_volume", "total_sell_unmatched_volume",
    "average_buy_trade_volume", "average_sell_trade_volume",
)
