"""Persistence-neutral contracts for canonical daily trading activity."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class TradeStatisticInstrumentRecord:
    instrument_id: int
    symbol: str
    instrument_type: str
    venue_code: str | None
    currency: str


@dataclass(frozen=True)
class DailyTradeStatisticWriteRecord:
    instrument_id: int
    trading_date: date
    source: str
    schema_version: int
    fetched_at: datetime
    market_cap: Decimal
    total_shares: Decimal
    matched_volume: Decimal
    matched_value: Decimal
    deal_volume: Decimal
    deal_value: Decimal
    total_volume: Decimal
    total_value: Decimal
    total_buy_trade: Decimal
    total_buy_trade_volume: Decimal
    total_sell_trade: Decimal
    total_sell_trade_volume: Decimal
    total_net_trade_volume: Decimal
    total_buy_unmatched_volume: Decimal
    total_sell_unmatched_volume: Decimal
    average_buy_trade_volume: Decimal
    average_sell_trade_volume: Decimal


@dataclass(frozen=True)
class DailyTradeStatisticRecord(DailyTradeStatisticWriteRecord):
    """Stored activity with the same canonical fields as a normalized write."""


class TradeStatisticsRepository(Protocol):
    def get_instrument(
        self, instrument_id: int,
    ) -> TradeStatisticInstrumentRecord | None: ...

    def upsert_rows(self, records: Iterable[DailyTradeStatisticWriteRecord]) -> int: ...

    def list_rows(
        self, instrument_id: int, start: date, end: date,
    ) -> tuple[DailyTradeStatisticRecord, ...]: ...
