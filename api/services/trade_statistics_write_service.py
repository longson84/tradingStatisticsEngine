"""Persist normalized activity only for its canonical Instrument/provider symbol."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pandas as pd

from api.repositories.instrument_routing_repository import InstrumentRoutingRepository
from api.repositories.trade_statistics_repository import (
    DailyTradeStatisticWriteRecord,
    TradeStatisticsRepository,
)
from api.services.trade_statistics_service import resolve_trade_statistics_instrument
from api.trade_statistics import (
    TRADE_STATISTIC_SCHEMA_VERSION,
    TRADE_STATISTIC_STORAGE_COLUMNS,
)


class TradeStatisticsWriteService:
    def __init__(
        self,
        repository: TradeStatisticsRepository,
        routing_repository: InstrumentRoutingRepository,
    ) -> None:
        self._repository = repository
        self._routing_repository = routing_repository

    def store_rows(
        self,
        instrument_id: int,
        symbol: str,
        rows: pd.DataFrame,
        *,
        source: str,
        fetched_at: datetime,
    ) -> int:
        if fetched_at.utcoffset() is None:
            raise ValueError("fetched_at must be timezone-aware")
        _, route = resolve_trade_statistics_instrument(
            self._repository, self._routing_repository, instrument_id,
        )
        if symbol.upper().strip() != route.provider_symbol:
            raise ValueError(
                f"Daily trade statistics for {symbol} cannot update instrument "
                f"{instrument_id} ({route.provider_symbol})"
            )
        required = ("symbol", "trading_date", *TRADE_STATISTIC_STORAGE_COLUMNS)
        missing = [name for name in required if name not in rows.columns]
        if missing:
            raise ValueError(f"Daily trade statistics are missing columns: {missing}")
        if not rows["symbol"].map(
            lambda value: isinstance(value, str) and value.upper().strip() == route.provider_symbol
        ).all():
            raise ValueError(
                f"Daily trade statistics row symbols cannot update instrument "
                f"{instrument_id} ({route.provider_symbol})"
            )
        return self._repository.upsert_rows(
            DailyTradeStatisticWriteRecord(
                instrument_id=instrument_id, trading_date=row["trading_date"],
                source=source, schema_version=TRADE_STATISTIC_SCHEMA_VERSION,
                fetched_at=fetched_at,
                **{name: Decimal(str(row[name])) for name in TRADE_STATISTIC_STORAGE_COLUMNS},
            )
            for row in rows.to_dict(orient="records")
        )
