"""Closed semantic catalog for VCI period session statistics."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


SessionStatisticMetricCode = Literal[
    "average_match_volume", "average_match_value", "average_deal_volume",
    "average_deal_value", "average_volume", "average_value",
    "total_match_volume", "total_match_value", "total_deal_volume",
    "total_deal_value", "total_volume", "total_value",
    "fr_buy_volume_total", "fr_buy_value_total", "fr_sell_volume_total",
    "fr_sell_value_total", "fr_net_volume_total", "fr_net_value_total",
    "fr_buy_volume_matched", "fr_buy_value_matched",
    "fr_sell_volume_matched", "fr_sell_value_matched",
    "fr_buy_volume_deal", "fr_buy_value_deal", "fr_sell_volume_deal",
    "fr_sell_value_deal", "fr_buy_volume_total_avg",
    "fr_buy_value_total_avg", "fr_sell_volume_total_avg",
    "fr_sell_value_total_avg", "fr_net_volume_total_avg",
    "fr_net_value_total_avg", "fr_buy_volume_matched_avg",
    "fr_buy_value_matched_avg", "fr_sell_volume_matched_avg",
    "fr_sell_value_matched_avg", "fr_buy_volume_deal_avg",
    "fr_buy_value_deal_avg", "fr_sell_volume_deal_avg",
    "fr_sell_value_deal_avg", "fr_net_volume_matched",
    "fr_net_value_matched", "fr_net_volume_matched_avg",
    "fr_net_value_matched_avg", "fr_net_volume_deal", "fr_net_value_deal",
    "fr_net_volume_deal_avg", "fr_net_value_deal_avg",
    "total_buy_trade_volume", "total_sell_trade_volume",
    "total_buy_trade_volume_avg", "total_sell_trade_volume_avg",
    "total_buy_trade", "total_sell_trade", "total_buy_trade_avg",
    "total_sell_trade_avg", "total_buy_unmatched_volume_avg",
    "total_sell_unmatched_volume_avg", "total_buy_unmatched_volume",
    "total_sell_unmatched_volume", "total_net_trade_volume",
    "total_net_trade_volume_avg", "average_buy_volume_per_trade",
    "average_sell_volume_per_trade",
]
SessionStatisticGroup = Literal[
    "market_activity", "foreign_activity", "trade_direction",
    "order_imbalance",
]
SessionStatisticUnit = Literal["volume", "value", "count"]
SESSION_STATISTIC_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class SessionStatisticMetricDefinition:
    code: SessionStatisticMetricCode
    group: SessionStatisticGroup
    label: str
    unit: SessionStatisticUnit
    order: int


_MARKET_ACTIVITY = (
    "average_match_volume", "average_match_value", "average_deal_volume",
    "average_deal_value", "average_volume", "average_value",
    "total_match_volume", "total_match_value", "total_deal_volume",
    "total_deal_value", "total_volume", "total_value",
)
_FOREIGN_ACTIVITY = (
    "fr_buy_volume_total", "fr_buy_value_total", "fr_sell_volume_total",
    "fr_sell_value_total", "fr_net_volume_total", "fr_net_value_total",
    "fr_buy_volume_matched", "fr_buy_value_matched",
    "fr_sell_volume_matched", "fr_sell_value_matched",
    "fr_buy_volume_deal", "fr_buy_value_deal", "fr_sell_volume_deal",
    "fr_sell_value_deal", "fr_buy_volume_total_avg",
    "fr_buy_value_total_avg", "fr_sell_volume_total_avg",
    "fr_sell_value_total_avg", "fr_net_volume_total_avg",
    "fr_net_value_total_avg", "fr_buy_volume_matched_avg",
    "fr_buy_value_matched_avg", "fr_sell_volume_matched_avg",
    "fr_sell_value_matched_avg", "fr_buy_volume_deal_avg",
    "fr_buy_value_deal_avg", "fr_sell_volume_deal_avg",
    "fr_sell_value_deal_avg", "fr_net_volume_matched",
    "fr_net_value_matched", "fr_net_volume_matched_avg",
    "fr_net_value_matched_avg", "fr_net_volume_deal", "fr_net_value_deal",
    "fr_net_volume_deal_avg", "fr_net_value_deal_avg",
)
_TRADE_DIRECTION = (
    "total_buy_trade_volume", "total_sell_trade_volume",
    "total_buy_trade_volume_avg", "total_sell_trade_volume_avg",
    "total_buy_trade", "total_sell_trade", "total_buy_trade_avg",
    "total_sell_trade_avg", "total_net_trade_volume",
    "total_net_trade_volume_avg",
)
_ORDER_IMBALANCE = (
    "total_buy_unmatched_volume_avg", "total_sell_unmatched_volume_avg",
    "total_buy_unmatched_volume", "total_sell_unmatched_volume",
    "average_buy_volume_per_trade", "average_sell_volume_per_trade",
)
_CODES = (
    *_MARKET_ACTIVITY,
    *_FOREIGN_ACTIVITY,
    *_TRADE_DIRECTION[:8],
    *_ORDER_IMBALANCE[:4],
    *_TRADE_DIRECTION[8:],
    *_ORDER_IMBALANCE[4:],
)
_COUNT_CODES = {
    "total_buy_trade", "total_sell_trade", "total_buy_trade_avg",
    "total_sell_trade_avg",
}


def _definition(code: str, order: int) -> SessionStatisticMetricDefinition:
    if code in _MARKET_ACTIVITY:
        group: SessionStatisticGroup = "market_activity"
    elif code in _FOREIGN_ACTIVITY:
        group = "foreign_activity"
    elif code in _TRADE_DIRECTION:
        group = "trade_direction"
    else:
        group = "order_imbalance"
    unit: SessionStatisticUnit = (
        "count" if code in _COUNT_CODES else "value" if "value" in code else "volume"
    )
    return SessionStatisticMetricDefinition(
        code=code,  # type: ignore[arg-type]
        group=group,
        label=code.replace("fr_", "foreign ").replace("_", " ").title(),
        unit=unit,
        order=order,
    )


SESSION_STATISTIC_METRICS = tuple(
    _definition(code, order) for order, code in enumerate(_CODES, 1)
)
SESSION_STATISTIC_METRIC_CODES = tuple(metric.code for metric in SESSION_STATISTIC_METRICS)
